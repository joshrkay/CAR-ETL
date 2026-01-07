"""Auth0 authentication and authorization utilities."""
from .config import Auth0Config, get_auth0_config
from .auth0_client import Auth0ManagementClient, Auth0TokenError, Auth0APIError
from .jwt_validator import JWTValidator, JWTClaims, JWTValidationError, get_jwt_validator
from .roles import Role, Permission, has_permission, require_role, has_any_role, get_role_permissions
from .rbac import RequiresRole, RequiresPermission
from .decorators import requires_role, RequiresRole, requires_permission
from .dependencies import get_current_user_claims, require_role as require_role_str, require_any_role

__all__ = [
    "Auth0Config",
    "get_auth0_config",
    "Auth0ManagementClient",
    "Auth0TokenError",
    "Auth0APIError",
    "JWTValidator",
    "JWTClaims",
    "JWTValidationError",
    "get_jwt_validator",
    "Role",
    "Permission",
    "has_permission",
    "require_role",
    "has_any_role",
    "get_role_permissions",
    "RequiresRole",
    "RequiresPermission",
    "requires_role",
    "RequiresRole",
    "requires_permission",
    "get_current_user_claims",
    "require_role_str",
    "require_any_role",
]
