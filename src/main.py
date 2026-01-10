"""Example FastAPI application with auth middleware."""
import logging
import signal
import sys
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.routes import ask as ask_routes
from src.api.routes import connectors as connector_routes
from src.api.routes import documents as document_routes
from src.api.routes import effective_rent as effective_rent_routes
from src.api.routes import health as health_routes
from src.api.routes import review as review_routes
from src.api.routes import upload as upload_routes
from src.api.routes.admin import flags as admin_flags
from src.api.routes.admin import tenants as admin_tenants
from src.api.routes.connectors import oauth_callback_public
from src.api.routes.webhooks import email as webhook_email_routes
from src.audit.logger import shutdown_all_audit_loggers
from src.auth.middleware import AuthMiddleware
from src.auth.models import AuthContext
from src.dependencies import get_current_user, get_feature_flags, require_role
from src.exceptions import CARException
from src.features.service import FeatureFlagService
from src.middleware.audit import AuditMiddleware
from src.middleware.error_handler import ErrorHandlerMiddleware
from src.middleware.request_id import RequestIDMiddleware

logger = logging.getLogger(__name__)

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


def _shutdown_handler(signum: int, frame: Any) -> None:
    """
    Signal handler for graceful shutdown.

    Handles SIGTERM and SIGINT to flush audit logs before exit.
    Note: Signal handlers run in the main thread and must be synchronous.
    FastAPI's shutdown event handler will handle async flush.
    """
    signal_name = signal.Signals(signum).name
    logger.info(
        f"Received {signal_name} signal, initiating graceful shutdown",
        extra={"signal": signal_name, "signum": signum},
    )

    # FastAPI's shutdown event will handle async flush
    # Signal handler just logs and lets FastAPI handle cleanup


# Register signal handlers for graceful shutdown
signal.signal(signal.SIGTERM, _shutdown_handler)
signal.signal(signal.SIGINT, _shutdown_handler)


@app.on_event("startup")
async def startup_event() -> None:
    """
    Validate environment variables and pre-warm Presidio models on application startup.

    This ensures all required credentials are configured before accepting requests
    and reduces latency on first redaction request by loading models during
    application initialization rather than on first use.
    """
    import logging

    from src.auth.config import get_auth_config
    from src.services.redaction import _get_analyzer, _get_anonymizer

    logger = logging.getLogger(__name__)

    # Step 1: Validate environment variables
    try:
        auth_config = get_auth_config()
        validation_errors = auth_config.validate_environment()

        if validation_errors:
            logger.error(
                "Environment variable validation failed",
                extra={
                    "error_count": len(validation_errors),
                    "errors": validation_errors,
                },
            )

            print("\n" + "=" * 80, file=sys.stderr)
            print("ERROR: Required environment variables are missing or invalid", file=sys.stderr)
            print("=" * 80, file=sys.stderr)
            print("\nMissing or invalid variables:", file=sys.stderr)
            for error in validation_errors:
                print(f"  - {error}", file=sys.stderr)
            print("\nTo fix this:", file=sys.stderr)
            print("  1. Create a .env file in the project root", file=sys.stderr)
            print("  2. Set all required environment variables", file=sys.stderr)
            print("  3. See docs/SECURITY.md for configuration details", file=sys.stderr)
            print("\nRequired variables:", file=sys.stderr)
            print("  - SUPABASE_URL", file=sys.stderr)
            print("  - SUPABASE_ANON_KEY", file=sys.stderr)
            print("  - SUPABASE_SERVICE_KEY", file=sys.stderr)
            print("  - SUPABASE_JWT_SECRET", file=sys.stderr)
            print("=" * 80 + "\n", file=sys.stderr)

            sys.exit(1)

        # Log success (without secrets)
        logger.info(
            "Environment variables validated successfully",
            extra={
                "supabase_url": auth_config.supabase_url,
                "app_env": auth_config.app_env,
                "log_level": auth_config.log_level,
                # Intentionally NOT logging secret values
            },
        )

    except Exception as e:
        logger.error(
            "Failed to validate environment variables",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        print("\n" + "=" * 80, file=sys.stderr)
        print("ERROR: Failed to load environment configuration", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        print(f"\nError: {e}", file=sys.stderr)
        print("\nTo fix this:", file=sys.stderr)
        print("  1. Ensure .env file exists in the project root", file=sys.stderr)
        print("  2. See docs/SECURITY.md for configuration details", file=sys.stderr)
        print("=" * 80 + "\n", file=sys.stderr)
        sys.exit(1)

    # Step 2: Pre-warm Presidio models
    try:
        # Pre-warm Presidio models
        _get_analyzer()
        _get_anonymizer()
        logger.info("Presidio models pre-warmed successfully")
    except Exception as e:
        logger.error(
            f"Failed to pre-warm Presidio models: {e}",
            exc_info=True,
        )
        # Don't fail startup - models will load on first use
        # This allows application to start even if Presidio has issues


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """
    FastAPI shutdown event handler.

    Flushes all audit log buffers before application exit.
    Ensures no audit events are lost during graceful shutdown.
    """
    logger.info("Application shutdown initiated, flushing audit logs")

    try:
        shutdown_all_audit_loggers(timeout=5.0)
        logger.info("Audit logs flushed successfully")
    except Exception as e:
        logger.error(
            f"Error flushing audit logs during shutdown: {e}",
            exc_info=True,
        )


# Register exception handlers for route handlers
# (Middleware also catches exceptions, but handlers are more idiomatic for FastAPI)
@app.exception_handler(CARException)
async def car_exception_handler(request: Request, exc: CARException) -> JSONResponse:
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
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
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
app.include_router(connector_routes.router)
app.include_router(ask_routes.router)
app.include_router(effective_rent_routes.router)
app.include_router(review_routes.router)
app.include_router(webhook_email_routes.router)

# Public OAuth callback route (outside router prefix)
app.add_api_route(
    "/oauth/microsoft/callback",
    oauth_callback_public,
    methods=["GET"],
    tags=["connectors", "sharepoint"],
    summary="OAuth callback (public)",
    description="Handle OAuth callback from Microsoft (public endpoint, validates state).",
)


@app.get("/me")
async def get_current_user_info(user: Annotated[AuthContext, Depends(get_current_user)]) -> dict[str, Any]:
    """Get current authenticated user info."""
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "tenant_id": str(user.tenant_id),
        "roles": user.roles,
        "tenant_slug": user.tenant_slug,
    }


@app.get("/admin")
async def admin_endpoint(user: Annotated[AuthContext, Depends(require_role("Admin"))]) -> dict[str, Any]:
    """Admin-only endpoint."""
    return {
        "message": "Admin access granted",
        "user_id": str(user.user_id),
    }


@app.get("/experimental-feature")
async def experimental_feature(
    flags: Annotated[FeatureFlagService, Depends(get_feature_flags)],
    user: Annotated[AuthContext, Depends(get_current_user)],
) -> dict[str, Any]:
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
