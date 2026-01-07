"""FastAPI decorators for RBAC enforcement."""
import logging
from typing import Callable, List, Optional, Union
from functools import wraps

from fastapi import HTTPException, status, Depends, Request
from fastapi.routing import APIRoute

from .jwt_validator import JWTClaims
from .roles import Role, Permission
from .permissions import has_any_role as check_has_any_role, has_permission as check_has_permission
from .dependencies import get_current_user_claims
from .audit import log_permission_denial, log_permission_granted

logger = logging.getLogger(__name__)


def requires_role(*required_roles: Union[str, Role]):
    """Decorator factory for role-based access control.
    
    Usage:
        @router.get("/admin-only")
        @requires_role("Admin")
        async def admin_endpoint(claims: JWTClaims = Depends(get_current_user_claims)):
            ...
    
    Or with multiple roles:
        @router.get("/documents")
        @requires_role("Admin", "Analyst")
        async def documents_endpoint(claims: JWTClaims = Depends(get_current_user_claims)):
            ...
    
    Args:
        *required_roles: One or more roles (strings or Role enums) required to access.
    
    Returns:
        Decorator function that checks roles.
    """
    # Convert string roles to Role enums
    role_enums: List[Role] = []
    role_strings: List[str] = []
    
    for role in required_roles:
        if isinstance(role, Role):
            role_enums.append(role)
            role_strings.append(role.value)
        elif isinstance(role, str):
            # Normalize to Role enum
            normalized = role.lower().strip()
            try:
                role_enum = Role(normalized)
                role_enums.append(role_enum)
                role_strings.append(role_enum.value)
            except ValueError:
                logger.warning(f"Invalid role in decorator: {role}")
                role_strings.append(role)
        else:
            logger.warning(f"Invalid role type in decorator: {type(role)}")
    
    def decorator(func: Callable) -> Callable:
        """Decorator that adds role check to function."""
        
        # Store original function
        original_func = func
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            """Wrapper that performs role check."""
            # Extract claims from kwargs
            claims: Optional[JWTClaims] = None
            
            for key, value in kwargs.items():
                if isinstance(value, JWTClaims):
                    claims = value
                    break
            
            if not claims:
                logger.error("JWTClaims not found in endpoint arguments")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Authentication context not available"
                )
            
            # Get endpoint path from request if available
            endpoint = None
            for arg in args:
                if hasattr(arg, 'url'):
                    endpoint = str(arg.url.path)
                    break
            
            # Check if user has any of the required roles
            user_roles = claims.roles or []
            
            if not check_has_any_role(user_roles, role_enums):
                log_permission_denial(
                    claims=claims,
                    required_roles=role_strings,
                    endpoint=endpoint,
                    reason="User does not have required role(s)"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required role(s): {', '.join(role_strings)}"
                )
            
            # Log successful access
            log_permission_granted(
                claims=claims,
                endpoint=endpoint,
                role=", ".join(role_strings)
            )
            
            return await original_func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Alias for acceptance criteria syntax: @RequiresRole('RoleName')
# This allows the exact syntax requested: @RequiresRole('Admin')
# Usage: @RequiresRole('Admin') or @RequiresRole('Analyst', 'Admin')
RequiresRole = requires_role


def requires_any_role(required_roles: List[Union[str, Role]]):
    """Decorator factory for multi-role access control (any of the roles).
    
    Usage:
        @router.get("/documents")
        @requires_any_role(["Admin", "Analyst"])
        async def documents_endpoint(claims: JWTClaims = Depends(get_current_user_claims)):
            ...
    
    Args:
        required_roles: List of roles (strings or Role enums) - user must have at least one.
    
    Returns:
        Decorator function that checks roles.
    """
    return requires_role(*required_roles)


def requires_permission(permission: Union[str, Permission]):
    """Decorator factory for permission-based access control.
    
    Usage:
        @router.post("/documents")
        @requires_permission("upload_document")
        async def upload_document(claims: JWTClaims = Depends(get_current_user_claims)):
            ...
    
    Args:
        permission: Permission (string or Permission enum) required to access.
    
    Returns:
        Decorator function that checks permission.
    """
    # Convert permission to Permission enum
    if isinstance(permission, Permission):
        permission_enum = permission
        permission_str = permission.value
    elif isinstance(permission, str):
        # Normalize permission string
        normalized = permission.lower().strip()
        try:
            permission_enum = Permission(normalized)
            permission_str = permission_enum.value
        except ValueError:
            logger.warning(f"Invalid permission in decorator: {permission}")
            permission_str = permission
            permission_enum = None
    else:
        logger.warning(f"Invalid permission type in decorator: {type(permission)}")
        permission_str = str(permission)
        permission_enum = None
    
    def decorator(func: Callable) -> Callable:
        """Decorator that adds permission check to function."""
        
        original_func = func
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            """Wrapper that performs permission check."""
            # Extract claims from kwargs
            claims: Optional[JWTClaims] = None
            
            for key, value in kwargs.items():
                if isinstance(value, JWTClaims):
                    claims = value
                    break
            
            if not claims:
                logger.error("JWTClaims not found in endpoint arguments")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Authentication context not available"
                )
            
            # Get endpoint path from request if available
            endpoint = None
            for arg in args:
                if hasattr(arg, 'url'):
                    endpoint = str(arg.url.path)
                    break
            
            # Check if user has the required permission
            user_roles = claims.roles or []
            
            if not permission_enum or not check_has_permission(user_roles, permission_enum):
                log_permission_denial(
                    claims=claims,
                    required_permission=permission_str,
                    endpoint=endpoint,
                    reason="User does not have required permission"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required permission: {permission_str}"
                )
            
            # Log successful access
            log_permission_granted(
                claims=claims,
                endpoint=endpoint,
                permission=permission_str
            )
            
            return await original_func(*args, **kwargs)
        
        return wrapper
    
    return decorator
