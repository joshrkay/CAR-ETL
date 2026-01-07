"""Permission checking logic for RBAC."""
import logging
from typing import List, Set, Optional
from functools import lru_cache

from .roles import Role, Permission, ROLE_PERMISSIONS, get_role_permissions

logger = logging.getLogger(__name__)


def normalize_role(role: str) -> str:
    """Normalize role string to lowercase for case-insensitive comparison.
    
    Args:
        role: Role string to normalize.
    
    Returns:
        Lowercase role string.
    """
    return role.lower().strip() if role else ""


@lru_cache(maxsize=128)
def get_role_from_string(role_str: str) -> Optional[Role]:
    """Get Role enum from string (case-insensitive, cached).
    
    Args:
        role_str: Role string.
    
    Returns:
        Role enum or None if invalid.
    """
    normalized = normalize_role(role_str)
    
    try:
        return Role(normalized)
    except ValueError:
        logger.warning(f"Invalid role string: {role_str}")
        return None


def has_permission(roles: List[str], permission: Permission) -> bool:
    """Check if any of the given roles has the specified permission.
    
    Args:
        roles: List of role strings from JWT claims (case-insensitive).
        permission: Permission to check.
    
    Returns:
        True if any role has the permission, False otherwise.
    """
    for role_str in roles:
        role = get_role_from_string(role_str)
        if role:
            role_perms = get_role_permissions(role)
            if permission in role_perms:
                return True
    
    return False


def has_any_permission(roles: List[str], permissions: List[Permission]) -> bool:
    """Check if any of the given roles has any of the specified permissions.
    
    Args:
        roles: List of role strings from JWT claims (case-insensitive).
        permissions: List of permissions to check.
    
    Returns:
        True if any role has any permission, False otherwise.
    """
    for permission in permissions:
        if has_permission(roles, permission):
            return True
    
    return False


def require_role(roles: List[str], required_role: Role) -> bool:
    """Check if user has the required role (case-insensitive).
    
    Args:
        roles: List of role strings from JWT claims.
        required_role: Required role.
    
    Returns:
        True if user has the required role, False otherwise.
    """
    for role_str in roles:
        role = get_role_from_string(role_str)
        if role == required_role:
            return True
    
    return False


def has_any_role(roles: List[str], required_roles: List[Role]) -> bool:
    """Check if user has any of the required roles (case-insensitive).
    
    Args:
        roles: List of role strings from JWT claims.
        required_roles: List of required roles.
    
    Returns:
        True if user has any required role, False otherwise.
    """
    user_roles: Set[Role] = set()
    
    for role_str in roles:
        role = get_role_from_string(role_str)
        if role:
            user_roles.add(role)
    
    return bool(user_roles & set(required_roles))


def get_user_permissions(roles: List[str]) -> Set[Permission]:
    """Get all permissions for a user based on their roles.
    
    Args:
        roles: List of role strings from JWT claims (case-insensitive).
    
    Returns:
        Set of all permissions the user has.
    """
    all_permissions: Set[Permission] = set()
    
    for role_str in roles:
        role = get_role_from_string(role_str)
        if role:
            role_perms = get_role_permissions(role)
            all_permissions.update(role_perms)
    
    return all_permissions
