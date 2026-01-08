"""FastAPI dependencies for authentication and feature flags."""
from fastapi import Request, HTTPException, status, Depends
from typing import Annotated, Union
from src.auth.models import AuthContext
from src.features.service import FeatureFlagService
from supabase import Client


def get_current_user(request: Request) -> AuthContext:
    """
    Dependency to get current authenticated user from request state.
    
    Raises:
        HTTPException: If user is not authenticated
    """
    auth: AuthContext | None = getattr(request.state, "auth", None)
    
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "NOT_AUTHENTICATED",
                "message": "User is not authenticated",
            },
        )
    
    return auth


def require_role(role: str):
    """
    Dependency factory to require a specific role.
    
    Usage:
        @app.get("/admin")
        async def admin_endpoint(user: Annotated[AuthContext, Depends(require_role("Admin"))]):
            ...
    """
    def role_checker(user: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not user.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "message": f"Role '{role}' is required",
                },
            )
        return user
    
    return role_checker


def require_any_role(roles: list[str]):
    """
    Dependency factory to require any of the specified roles.
    
    Usage:
        @app.get("/manager")
        async def manager_endpoint(user: Annotated[AuthContext, Depends(require_any_role(["Admin", "Manager"]))]):
            ...
    """
    def role_checker(user: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not user.has_any_role(roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "message": f"One of the following roles is required: {', '.join(roles)}",
                },
            )
        return user
    
    return role_checker


def get_supabase_client(request: Request) -> Client:
    """
    Get Supabase client from request state (created by middleware with user's JWT).
    
    This client uses the user's JWT token and respects RLS policies.
    The client is created by AuthMiddleware and attached to request.state.supabase.
    
    Raises:
        HTTPException: If client is not in request state (user not authenticated)
    """
    client: Union[Client, None] = getattr(request.state, "supabase", None)
    
    if not client:
        # Client should be created by AuthMiddleware
        # If it's missing, user is not authenticated
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "NOT_AUTHENTICATED",
                "message": "Supabase client not available. User must be authenticated.",
            },
        )
    
    return client


def get_feature_flags(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
) -> FeatureFlagService:
    """
    Dependency to get feature flag service for current tenant.
    
    Usage:
        @app.get("/experimental-feature")
        async def experimental(flags: FeatureFlagService = Depends(get_feature_flags)):
            if not await flags.is_enabled("experimental_search"):
                raise HTTPException(404, "Feature not available")
            return {"data": "experimental results"}
    """
    supabase = get_supabase_client(request)
    return FeatureFlagService(supabase, auth.tenant_id)


def get_service_client() -> Client:
    """
    Get Supabase client with service_role key (bypasses RLS).
    
    WARNING: This client bypasses RLS and should ONLY be used for:
    - Admin operations (tenant provisioning, system configuration)
    - Background jobs
    - Operations that require cross-tenant access
    
    NEVER use this for regular user requests.
    
    Returns:
        Supabase client with service_role key (bypasses RLS)
    """
    from src.auth.client import create_service_client
    return create_service_client()


def get_audit_logger(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_user)],
):
    """
    Dependency to get audit logger for current tenant and user.
    
    Usage:
        from src.audit.logger import AuditLogger
        from src.audit.models import EventType, ActionType, ResourceType
        
        @app.post("/documents")
        async def upload_document(
            logger: AuditLogger = Depends(get_audit_logger),
        ):
            # ... upload logic ...
            await logger.log(
                event_type=EventType.DOCUMENT_UPLOAD,
                action=ActionType.CREATE,
                resource_type=ResourceType.DOCUMENT,
                resource_id=doc_id,
            )
            await logger.flush()  # Ensure event is persisted
    """
    from src.audit.logger import AuditLogger
    
    supabase = get_supabase_client(request)
    return AuditLogger(
        supabase=supabase,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
    )
