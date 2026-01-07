"""FastAPI dependencies for authentication."""
from fastapi import Request, HTTPException, status, Depends
from typing import Annotated
from src.auth.models import AuthContext


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
