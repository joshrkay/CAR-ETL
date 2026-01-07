"""Role definitions and permissions for CAR Platform RBAC."""
from enum import Enum
from typing import Set, List


class Role(str, Enum):
    """User roles in CAR Platform."""
    
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
    INGESTION = "ingestion"  # Service account role for document ingestion


class Permission(str, Enum):
    """Permissions that can be granted to roles."""
    
    # User Management
    CREATE_USER = "create_user"
    DELETE_USER = "delete_user"
    UPDATE_USER = "update_user"
    LIST_USERS = "list_users"
    
    # Tenant Management
    MODIFY_TENANT_SETTINGS = "modify_tenant_settings"
    VIEW_TENANT_SETTINGS = "view_tenant_settings"
    
    # Billing
    ACCESS_BILLING = "access_billing"
    VIEW_BILLING = "view_billing"
    
    # Document Operations
    UPLOAD_DOCUMENT = "upload_document"
    EDIT_DOCUMENT = "edit_document"
    DELETE_DOCUMENT = "delete_document"
    VIEW_DOCUMENT = "view_document"
    SEARCH_DOCUMENTS = "search_documents"
    
    # AI Operations
    OVERRIDE_AI_DECISION = "override_ai_decision"
    TRAIN_MODEL = "train_model"
    
    # System Operations
    SYSTEM_ADMIN = "system_admin"


# Role-Permission Mapping
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        # User Management
        Permission.CREATE_USER,
        Permission.DELETE_USER,
        Permission.UPDATE_USER,
        Permission.LIST_USERS,
        # Tenant Management
        Permission.MODIFY_TENANT_SETTINGS,
        Permission.VIEW_TENANT_SETTINGS,
        # Billing
        Permission.ACCESS_BILLING,
        Permission.VIEW_BILLING,
        # Document Operations
        Permission.UPLOAD_DOCUMENT,
        Permission.EDIT_DOCUMENT,
        Permission.DELETE_DOCUMENT,
        Permission.VIEW_DOCUMENT,
        Permission.SEARCH_DOCUMENTS,
        # AI Operations
        Permission.OVERRIDE_AI_DECISION,
        Permission.TRAIN_MODEL,
        # System Operations
        Permission.SYSTEM_ADMIN,
    },
    Role.ANALYST: {
        # Document Operations
        Permission.UPLOAD_DOCUMENT,
        Permission.EDIT_DOCUMENT,
        Permission.DELETE_DOCUMENT,
        Permission.VIEW_DOCUMENT,
        Permission.SEARCH_DOCUMENTS,
        # AI Operations
        Permission.OVERRIDE_AI_DECISION,
        # Tenant Management (read-only)
        Permission.VIEW_TENANT_SETTINGS,
    },
    Role.VIEWER: {
        # Document Operations (read-only)
        Permission.VIEW_DOCUMENT,
        Permission.SEARCH_DOCUMENTS,
        # Tenant Management (read-only)
        Permission.VIEW_TENANT_SETTINGS,
    },
    Role.INGESTION: {
        # Document Operations (ingestion only)
        Permission.UPLOAD_DOCUMENT,
        Permission.VIEW_DOCUMENT,
        Permission.SEARCH_DOCUMENTS,
        # No user management, no AI operations, no tenant settings modification
    },
}


def get_role_permissions(role: Role) -> Set[Permission]:
    """Get permissions for a role.
    
    Args:
        role: User role.
    
    Returns:
        Set of permissions for the role.
    """
    return ROLE_PERMISSIONS.get(role, set())


# Note: Permission checking functions moved to src/auth/permissions.py
# These are kept for backward compatibility but delegate to permissions module
def has_permission(roles: List[str], permission: Permission) -> bool:
    """Check if any of the given roles has the specified permission.
    
    DEPRECATED: Use src.auth.permissions.has_permission() instead.
    
    Args:
        roles: List of role strings from JWT claims.
        permission: Permission to check.
    
    Returns:
        True if any role has the permission, False otherwise.
    """
    from .permissions import has_permission as _has_permission
    return _has_permission(roles, permission)


def has_any_role(roles: List[str], required_roles: List[Role]) -> bool:
    """Check if user has any of the required roles.
    
    DEPRECATED: Use src.auth.permissions.has_any_role() instead.
    
    Args:
        roles: List of role strings from JWT claims.
        required_roles: List of required roles.
    
    Returns:
        True if user has any required role, False otherwise.
    """
    from .permissions import has_any_role as _has_any_role
    return _has_any_role(roles, required_roles)


def require_role(roles: List[str], required_role: Role) -> bool:
    """Check if user has the required role.
    
    DEPRECATED: Use src.auth.permissions.require_role() instead.
    
    Args:
        roles: List of role strings from JWT claims.
        required_role: Required role.
    
    Returns:
        True if user has the required role, False otherwise.
    """
    from .permissions import require_role as _require_role
    return _require_role(roles, required_role)
