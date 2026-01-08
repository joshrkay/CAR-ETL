"""FastAPI dependencies for authentication and feature flags."""
from fastapi import Request, HTTPException, status, Depends
from typing import Annotated
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
    Get or create Supabase client.
    
    Creates client from config if not in request state.
    """
    client: Client | None = getattr(request.state, "supabase", None)
    
    if not client:
        from supabase import create_client
        from src.auth.config import get_auth_config
        
        config = get_auth_config()
        client = create_client(
            config.supabase_url,
            config.supabase_service_key,
        )
        request.state.supabase = client
    
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
