"""Role-Based Access Control (RBAC) dependencies for FastAPI with caching."""
import logging
from typing import Optional, Union
from functools import lru_cache

from fastapi import HTTPException, status, Depends, Request

from .jwt_validator import JWTClaims
from .roles import Role, Permission
from .permissions import has_any_role, has_permission
from .dependencies import get_current_user_claims
from .audit import log_permission_denial, log_permission_granted

logger = logging.getLogger(__name__)


# Request-scoped cache for role checks (per request, not global)
# This is a simple in-memory cache that gets cleared after each request
_request_cache: dict = {}


def _get_cache_key(tenant_id: str, user_id: str, roles: tuple) -> str:
    """Generate cache key for role check.
    
    Args:
        tenant_id: Tenant identifier.
        user_id: User identifier.
        roles: Tuple of user roles.
    
    Returns:
        Cache key string.
    """
    return f"{tenant_id}:{user_id}:{':'.join(sorted(roles))}"


def RequiresRole(*required_roles: Union[Role, str]):
    """Create FastAPI dependency that requires one or more roles (with caching).
    
    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(
            claims: JWTClaims = Depends(RequiresRole(Role.ADMIN))
        ):
            ...
    
    Args:
        *required_roles: One or more roles (Role enum or string) required to access.
    
    Returns:
        FastAPI dependency function.
    """
    # Normalize roles to Role enums
    role_enums: list[Role] = []
    role_strings: list[str] = []
    
    for role in required_roles:
        if isinstance(role, Role):
            role_enums.append(role)
            role_strings.append(role.value)
        elif isinstance(role, str):
            normalized = role.lower().strip()
            try:
                role_enum = Role(normalized)
                role_enums.append(role_enum)
                role_strings.append(role_enum.value)
            except ValueError:
                logger.warning(f"Invalid role in RequiresRole: {role}")
                role_strings.append(role)
    
    async def role_checker(
        request: Request,
        claims: JWTClaims = Depends(get_current_user_claims)
    ) -> JWTClaims:
        """Check if user has any of the required roles (cached per request)."""
        # Generate cache key
        cache_key = _get_cache_key(
            claims.tenant_id or "",
            claims.user_id or "",
            tuple(claims.roles or [])
        )
        
        # Check cache (per request)
        if hasattr(request.state, 'rbac_cache'):
            cache = request.state.rbac_cache
        else:
            cache = {}
            request.state.rbac_cache = cache
        
        cache_key_full = f"role:{':'.join(role_strings)}"
        
        if cache_key_full in cache:
            cached_result = cache[cache_key_full]
            if cached_result:
                log_permission_granted(
                    claims=claims,
                    endpoint=str(request.url.path),
                    role=", ".join(role_strings)
                )
            return claims
        
        # Perform role check
        user_roles = claims.roles or []
        has_access = has_any_role(user_roles, role_enums)
        
        # Cache result (for this request only)
        cache[cache_key_full] = has_access
        
        if not has_access:
            log_permission_denial(
                claims=claims,
                required_roles=role_strings,
                endpoint=str(request.url.path),
                reason="User does not have required role(s)"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role(s): {', '.join(role_strings)}"
            )
        
        log_permission_granted(
            claims=claims,
            endpoint=str(request.url.path),
            role=", ".join(role_strings)
        )
        
        return claims
    
    return role_checker


def RequiresPermission(permission: Union[Permission, str]):
    """Create FastAPI dependency that requires a specific permission (with caching).
    
    Usage:
        @router.post("/documents")
        async def upload_document(
            claims: JWTClaims = Depends(RequiresPermission(Permission.UPLOAD_DOCUMENT))
        ):
            ...
    
    Args:
        permission: Permission (Permission enum or string) required to access.
    
    Returns:
        FastAPI dependency function.
    """
    # Normalize permission to Permission enum
    if isinstance(permission, Permission):
        permission_enum = permission
        permission_str = permission.value
    elif isinstance(permission, str):
        normalized = permission.lower().strip()
        try:
            permission_enum = Permission(normalized)
            permission_str = permission_enum.value
        except ValueError:
            logger.warning(f"Invalid permission in RequiresPermission: {permission}")
            permission_str = permission
            permission_enum = None
    else:
        logger.warning(f"Invalid permission type in RequiresPermission: {type(permission)}")
        permission_str = str(permission)
        permission_enum = None
    
    async def permission_checker(
        request: Request,
        claims: JWTClaims = Depends(get_current_user_claims)
    ) -> JWTClaims:
        """Check if user has required permission (cached per request)."""
        if not permission_enum:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid permission: {permission_str}"
            )
        
        # Generate cache key
        cache_key = _get_cache_key(
            claims.tenant_id or "",
            claims.user_id or "",
            tuple(claims.roles or [])
        )
        
        # Check cache (per request)
        if hasattr(request.state, 'rbac_cache'):
            cache = request.state.rbac_cache
        else:
            cache = {}
            request.state.rbac_cache = cache
        
        cache_key_full = f"permission:{permission_str}"
        
        if cache_key_full in cache:
            cached_result = cache[cache_key_full]
            if cached_result:
                log_permission_granted(
                    claims=claims,
                    endpoint=str(request.url.path),
                    permission=permission_str
                )
            return claims
        
        # Perform permission check
        user_roles = claims.roles or []
        has_access = has_permission(user_roles, permission_enum)
        
        # Cache result (for this request only)
        cache[cache_key_full] = has_access
        
        if not has_access:
            log_permission_denial(
                claims=claims,
                required_permission=permission_str,
                endpoint=str(request.url.path),
                reason="User does not have required permission"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required permission: {permission_str}"
            )
        
        log_permission_granted(
            claims=claims,
            endpoint=str(request.url.path),
            permission=permission_str
        )
        
        return claims
    
    return permission_checker
