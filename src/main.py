"""Example FastAPI application with auth middleware."""
from fastapi import FastAPI, Depends, HTTPException, Request, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Annotated
from src.auth.middleware import AuthMiddleware
from src.auth.models import AuthContext
from src.dependencies import get_current_user, require_role, get_feature_flags
from src.features.service import FeatureFlagService
from src.api.routes.admin import flags as admin_flags
from src.api.routes.admin import tenants as admin_tenants
from src.api.routes import health as health_routes
from src.api.routes import documents as document_routes
from src.api.routes import upload as upload_routes
from src.middleware.audit import AuditMiddleware
from src.middleware.request_id import RequestIDMiddleware
from src.middleware.error_handler import ErrorHandlerMiddleware
from src.exceptions import CARException

app = FastAPI(title="CAR Platform API", version="1.0.0")

# Middleware order (last added = outermost, executes first):
# 1. RequestIDMiddleware - generates request_id (innermost, executes early)
# 2. AuthMiddleware - validates authentication
# 3. AuditMiddleware - logs requests
# 4. ErrorHandlerMiddleware - catches all exceptions (outermost, executes first)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(ErrorHandlerMiddleware)


# Register exception handlers for route handlers
# (Middleware also catches exceptions, but handlers are more idiomatic for FastAPI)
@app.exception_handler(CARException)
async def car_exception_handler(request: Request, exc: CARException):
    """
    Handle CAR Platform custom exceptions.
    
    CRITICAL: Client errors (4xx) are never converted to 500.
    Only unknown CARException types default to 500.
    """
    request_id = getattr(request.state, "request_id", None)
    
    error_response = {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
            "request_id": request_id,
        }
    }
    
    # Map exception type to status code
    # All mapped codes are client errors (4xx) - never 500
    from fastapi import status
    status_code_map = {
        "VALIDATION_ERROR": status.HTTP_400_BAD_REQUEST,  # 400 - Client error
        "AUTHENTICATION_ERROR": status.HTTP_401_UNAUTHORIZED,  # 401 - Client error
        "PERMISSION_ERROR": status.HTTP_403_FORBIDDEN,  # 403 - Client error
        "NOT_FOUND": status.HTTP_404_NOT_FOUND,  # 404 - Client error
        "RATE_LIMIT_ERROR": status.HTTP_429_TOO_MANY_REQUESTS,  # 429 - Client error
    }
    
    status_code = status_code_map.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Add retry_after for rate limit errors
    if hasattr(exc, "retry_after"):
        error_response["error"]["retry_after"] = exc.retry_after
    
    return JSONResponse(status_code=status_code, content=error_response)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle FastAPI request validation errors."""
    request_id = getattr(request.state, "request_id", None)
    
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
    
    return JSONResponse(
        status_code=400,
        content=error_response,
    )


# Include routes
app.include_router(health_routes.router)
app.include_router(admin_flags.router)
app.include_router(admin_tenants.router)
app.include_router(document_routes.router)
app.include_router(upload_routes.router)


@app.get("/me")
async def get_current_user_info(user: Annotated[AuthContext, Depends(get_current_user)]):
    """Get current authenticated user info."""
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "tenant_id": str(user.tenant_id),
        "roles": user.roles,
        "tenant_slug": user.tenant_slug,
    }


@app.get("/admin")
async def admin_endpoint(user: Annotated[AuthContext, Depends(require_role("Admin"))]):
    """Admin-only endpoint."""
    return {
        "message": "Admin access granted",
        "user_id": str(user.user_id),
    }


@app.get("/experimental-feature")
async def experimental_feature(
    flags: Annotated[FeatureFlagService, Depends(get_feature_flags)],
    user: Annotated[AuthContext, Depends(get_current_user)],
):
    """
    Example endpoint using feature flags.
    
    This endpoint is only accessible if the 'experimental_search' feature flag
    is enabled for the current tenant.
    """
    if not await flags.is_enabled("experimental_search"):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "FEATURE_NOT_AVAILABLE",
                "message": "This feature is not available for your tenant",
            },
        )
    
    return {
        "data": "experimental results",
        "message": "You have access to the experimental feature!",
    }


