"""Audit middleware for automatic request logging."""
import time
import logging
from typing import Awaitable, Callable, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.audit.logger import AuditLogger
from src.audit.models import EventType, ActionType
from src.dependencies import get_supabase_client

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically log all API requests.
    
    Logs:
    - Endpoint path
    - HTTP method
    - Status code
    - Request duration
    - IP address
    - User agent
    
    Non-blocking: audit failures don't affect request handling.
    """
    
    SKIP_PATHS = ["/health", "/docs", "/openapi.json", "/redoc"]
    
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and log audit event."""
        # Skip audit for health checks and docs
        if any(request.url.path.startswith(path) for path in self.SKIP_PATHS):
            return await call_next(request)
        
        # Extract request metadata
        start_time = time.time()
        method = request.method
        path = request.url.path
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent")
        
        # Execute request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        status_code = response.status_code
        
        # Log audit event (non-blocking)
        await self._log_request(
            request=request,
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "unknown"
    
    async def _log_request(
        self,
        request: Request,
        method: str,
        path: str,
        status_code: int,
        duration_ms: int,
        ip_address: str,
        user_agent: Optional[str],
    ) -> None:
        """
        Log API request as audit event.
        
        Non-blocking: errors are logged but don't affect response.
        """
        try:
            # Get auth context (may not exist for unauthenticated requests)
            auth = getattr(request.state, "auth", None)
            
            if not auth:
                # Skip logging for unauthenticated requests (already handled by auth middleware)
                return
            
            # Get Supabase client (with user's JWT for RLS)
            try:
                supabase = get_supabase_client(request)
            except Exception:
                # Can't log if we can't get client
                logger.warning(f"Could not get Supabase client for audit logging on {path}")
                return
            
            # Determine action type from HTTP method
            action = self._map_method_to_action(method)
            
            # Create audit logger
            audit_logger = AuditLogger(
                supabase=supabase,
                tenant_id=auth.tenant_id,
                user_id=auth.user_id,
            )
            
            # Log request event
            await audit_logger.log(
                event_type=EventType.API_REQUEST,
                action=action,
                resource_type="api",
                resource_id=path,
                metadata={
                    "method": method,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
                ip_address=ip_address,
                user_agent=user_agent,
            )
            
            # Flush buffer to ensure event is persisted
            await audit_logger.flush()
            
        except Exception as e:
            # Log error but don't block request
            logger.error(
                f"Failed to log audit event for {method} {path}: {e}",
                exc_info=True,
            )
    
    def _map_method_to_action(self, method: str) -> str:
        """Map HTTP method to action type."""
        method_upper = method.upper()
        if method_upper in ["POST", "PUT"]:
            return ActionType.CREATE
        elif method_upper == "GET":
            return ActionType.READ
        elif method_upper == "PATCH":
            return ActionType.UPDATE
        elif method_upper == "DELETE":
            return ActionType.DELETE
        else:
            return ActionType.READ  # Default to read
