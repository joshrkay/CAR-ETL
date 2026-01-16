"""Role-Based Access Control (RBAC) permission system."""
from typing import Dict, List


PERMISSIONS: Dict[str, List[str]] = {
    "Admin": ["*"],  # All permissions
    "Analyst": [
        "documents:read",
        "documents:write",
        "documents:delete",
        "search:read",
        "ask:read",
        "extractions:read",
        "extractions:override",
        "exports:read",
        "exports:write",
        "entities:merge",
        "connectors:read",
        "connectors:write",
    ],
    "Viewer": [
        "documents:read",
        "search:read",
        "ask:read",
        "extractions:read",
        "exports:read",
    ],
}


def has_permission(roles: List[str], permission: str) -> bool:
    """
    Check if any role grants the permission.
    
    Args:
        roles: List of user roles (case-insensitive comparison)
        permission: Permission string to check (e.g., "documents:read")
        
    Returns:
        True if any role grants the permission, False otherwise
        
    Note:
        Role comparison is case-insensitive. Admin role with "*" grants all permissions.
    """
    for role in roles:
        role_normalized = role.strip().capitalize()
        role_perms = PERMISSIONS.get(role_normalized, [])
        
        if "*" in role_perms or permission in role_perms:
            return True
    
    return False
