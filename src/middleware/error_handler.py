"""Error handler middleware for consistent error responses."""
import logging
from typing import Any, Awaitable, Callable, Dict, Optional, cast
from fastapi import Request, status, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from src.exceptions import (
    CARException,
    ValidationError,
    AuthenticationError,
    PermissionError,
    NotFoundError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle exceptions and return consistent error responses.
    
    Maps exceptions to HTTP status codes:
    - ValidationError → 400
    - AuthenticationError → 401
    - PermissionError → 403
    - NotFoundError → 404
    - RateLimitError → 429
    - Unhandled → 500 (logs full trace, returns generic message)
    """
    
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and handle exceptions."""
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            return await self._handle_exception(request, exc)
    
    async def _handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """
        Handle exception and return standardized error response.
        
        Args:
            request: FastAPI request object
            exc: Exception that was raised
            
        Returns:
            JSONResponse with standardized error format
        """
        # Get request ID from request state
        request_id = getattr(request.state, "request_id", None)
        
        # Handle FastAPI validation errors
        if isinstance(exc, RequestValidationError):
            return self._handle_validation_error(exc, request_id)
        
        # Handle FastAPI HTTPException
        if isinstance(exc, HTTPException):
            return self._handle_http_exception(exc, request_id)
        
        # Handle custom CAR exceptions
        if isinstance(exc, CARException):
            return self._handle_car_exception(exc, request_id)
        
        # Handle unhandled exceptions
        return self._handle_unhandled_exception(exc, request_id)
    
    def _handle_validation_error(
        self,
        exc: RequestValidationError,
        request_id: Optional[str],
    ) -> JSONResponse:
        """Handle FastAPI request validation errors."""
        details = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error.get("loc", []))
            issue = error.get("msg", "Invalid value")
            details.append({"field": field, "issue": issue})
        
        error_response = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": details,
                "request_id": request_id,
            }
        }
        
        logger.warning(
            f"Validation error [request_id={request_id}]: {details}",
            extra={"request_id": request_id},
        )
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response,
        )
    
    def _handle_http_exception(
        self,
        exc: HTTPException,
        request_id: Optional[str],
    ) -> JSONResponse:
        """
        Handle FastAPI HTTPException and convert to standard format.
        
        CRITICAL: Preserves original status code - client errors (4xx) stay as 4xx,
        never converted to 500.
        """
        # Extract error details from HTTPException
        detail = exc.detail
        
        # Preserve the original status code - never override client errors (4xx) with 500
        status_code = exc.status_code
        
        details: list[Dict[str, str]] = []

        # If detail is already a dict with code/message, use it
        if isinstance(detail, dict):
            code = detail.get("code", "HTTP_ERROR")
            message = detail.get("message", str(detail))
            details = cast(list[Dict[str, str]], detail.get("details", []))
        else:
            # Convert string detail to standard format
            code = "HTTP_ERROR"
            message = str(detail) if detail else "An error occurred"
        
        error_response = {
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": request_id,
            }
        }
        
        # Log client errors as warnings, server errors as errors
        log_level = logging.WARNING if 400 <= status_code < 500 else logging.ERROR
        logger.log(
            log_level,
            f"{code} [request_id={request_id}]: {message} (status={status_code})",
            extra={"request_id": request_id, "error_code": code, "status_code": status_code},
        )
        
        return JSONResponse(
            status_code=status_code,
            content=error_response,
        )
    
    def _handle_car_exception(
        self,
        exc: CARException,
        request_id: Optional[str],
    ) -> JSONResponse:
        """
        Handle custom CAR Platform exceptions.
        
        CRITICAL: Client errors (4xx) are never converted to 500.
        Only unknown CARException types default to 500.
        """
        # Map exception type to HTTP status code
        # All mapped exceptions are client errors (4xx) - never 500
        status_code_map = {
            ValidationError: status.HTTP_400_BAD_REQUEST,  # 400 - Client error
            AuthenticationError: status.HTTP_401_UNAUTHORIZED,  # 401 - Client error
            PermissionError: status.HTTP_403_FORBIDDEN,  # 403 - Client error
            NotFoundError: status.HTTP_404_NOT_FOUND,  # 404 - Client error
            RateLimitError: status.HTTP_429_TOO_MANY_REQUESTS,  # 429 - Client error
        }
        
        # Get status code - only defaults to 500 for unknown CARException types
        status_code = status_code_map.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        error_response: Dict[str, Any] = {
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id,
            }
        }
        
        # Add retry_after for rate limit errors
        if isinstance(exc, RateLimitError):
            error_response["error"]["retry_after"] = exc.retry_after
        
        # Log error with context
        log_level = logging.WARNING if status_code < 500 else logging.ERROR
        logger.log(
            log_level,
            f"{exc.code} [request_id={request_id}]: {exc.message}",
            extra={"request_id": request_id, "error_code": exc.code},
        )
        
        return JSONResponse(
            status_code=status_code,
            content=error_response,
        )
    
    def _handle_unhandled_exception(
        self,
        exc: Exception,
        request_id: Optional[str],
    ) -> JSONResponse:
        """Handle unhandled exceptions (500 errors)."""
        # Log full traceback for debugging
        logger.error(
            f"Unhandled exception [request_id={request_id}]: {type(exc).__name__}: {str(exc)}",
            exc_info=True,
            extra={"request_id": request_id},
        )
        
        # Return generic error message (don't expose stack trace)
        error_response: Dict[str, Any] = {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "details": [],
                "request_id": request_id,
            }
        }
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response,
        )
