"""FastAPI dependencies for RBAC permission enforcement."""
import inspect
import logging
from typing import Any, Awaitable, Callable
from fastapi import Depends, HTTPException, Request, status

from src.auth.models import AuthContext
from src.auth.rbac import has_permission
from src.dependencies import get_current_user


logger = logging.getLogger(__name__)


def _log_permission_denial(
    user_id: str,
    tenant_id: str,
    permission: str,
    endpoint: str,
    roles: list[str],
) -> None:
    """
    Log permission denial for audit purposes.
    
    Args:
        user_id: User UUID
        tenant_id: Tenant UUID
        permission: Required permission that was denied
        endpoint: API endpoint path
        roles: User's current roles
    """
    logger.warning(
        "Permission denied",
        extra={
            "event_type": "PERMISSION_DENIED",
            "user_id": user_id,
            "tenant_id": tenant_id,
            "permission": permission,
            "endpoint": endpoint,
            "user_roles": roles,
        },
    )


def require_permission(
    permission: str,
) -> Callable[[Request], Awaitable[AuthContext]]:
    """
    Dependency factory to require a specific permission.
    
    Usage:
        @router.delete("/documents/{id}")
        async def delete_document(
            id: UUID,
            request: Request,
            auth: AuthContext = Depends(require_permission("documents:delete"))
        ):
            ...
    
    Args:
        permission: Permission string to require (e.g., "documents:delete")
        
    Returns:
        FastAPI dependency that checks permission and returns AuthContext
    """
    async def checker(
        request: Request,
        auth: AuthContext = Depends(get_current_user),
    ) -> AuthContext:
        if not has_permission(auth.roles, permission):
            _log_permission_denial(
                user_id=str(auth.user_id),
                tenant_id=str(auth.tenant_id),
                permission=permission,
                endpoint=request.url.path,
                roles=auth.roles,
            )
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PERMISSION_DENIED",
                    "message": f"Required permission: {permission}",
                    "your_roles": auth.roles,
                },
            )
        
        return auth
    
    return checker


def require_permission_dependency(permission: str) -> Callable[[Request], Awaitable[AuthContext]]:
    """
    Resolve permission checks at request time for easier patching in tests.

    This helper defers the call to require_permission until the dependency
    is executed, allowing test suites to patch require_permission reliably.
    """
    async def dependency(
        request: Request,
        auth: AuthContext = Depends(get_current_user),
    ) -> AuthContext:
        checker: Any = require_permission(permission)
        parameters = inspect.signature(checker).parameters
        if len(parameters) >= 2:
            result = checker(request, auth)
        elif len(parameters) == 1:
            result = checker(request)
        else:
            result = checker()
        if inspect.isawaitable(result):
            return await result
        return result

    return dependency


# Role shortcuts for convenience
# These can be used directly in endpoint signatures:
#   auth: AuthContext = Depends(RequireAdmin)
def RequireAdmin(request: Request, auth: AuthContext = Depends(require_permission("*"))) -> AuthContext:
    """Dependency shortcut requiring Admin role (all permissions)."""
    return auth


def RequireAnalyst(request: Request, auth: AuthContext = Depends(require_permission("documents:write"))) -> AuthContext:
    """Dependency shortcut requiring Analyst role (documents:write permission)."""
    return auth


def RequireViewer(request: Request, auth: AuthContext = Depends(require_permission("documents:read"))) -> AuthContext:
    """Dependency shortcut requiring Viewer role (documents:read permission)."""
    return auth
