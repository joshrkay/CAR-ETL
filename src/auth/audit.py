"""Audit logging for RBAC access control."""
import logging
import asyncio
from datetime import datetime
from typing import Optional

from .jwt_validator import JWTClaims

logger = logging.getLogger(__name__)

# Import S3 audit logger (optional, fails gracefully if not configured)
try:
    from ..audit.service import audit_log as s3_audit_log
    S3_AUDIT_AVAILABLE = True
except (ImportError, Exception):
    S3_AUDIT_AVAILABLE = False
    logger.warning("S3 audit logging not available (boto3 not installed or not configured)")


def log_permission_denial(
    claims: JWTClaims,
    required_role: Optional[str] = None,
    required_roles: Optional[list[str]] = None,
    required_permission: Optional[str] = None,
    endpoint: Optional[str] = None,
    reason: Optional[str] = None
) -> None:
    """Log permission denial for audit purposes.
    
    Args:
        claims: JWT claims of the user attempting access.
        required_role: Required role (if role-based check).
        required_roles: Required roles (if multi-role check).
        required_permission: Required permission (if permission-based check).
        endpoint: Endpoint path that was accessed.
        reason: Additional reason for denial.
    """
    audit_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": claims.user_id,
        "tenant_id": claims.tenant_id,
        "user_roles": claims.roles,
        "endpoint": endpoint,
        "denial_type": None,
        "required": None,
        "reason": reason
    }
    
    if required_role:
        audit_data["denial_type"] = "role"
        audit_data["required"] = required_role
    elif required_roles:
        audit_data["denial_type"] = "roles"
        audit_data["required"] = required_roles
    elif required_permission:
        audit_data["denial_type"] = "permission"
        audit_data["required"] = required_permission
    
    # Log as structured data for audit trail
    logger.warning(
        f"RBAC_PERMISSION_DENIED: "
        f"user_id={audit_data['user_id']}, "
        f"tenant_id={audit_data['tenant_id']}, "
        f"user_roles={audit_data['user_roles']}, "
        f"denial_type={audit_data['denial_type']}, "
        f"required={audit_data['required']}, "
        f"endpoint={audit_data['endpoint']}"
    )


def log_permission_granted(
    claims: JWTClaims,
    endpoint: Optional[str] = None,
    role: Optional[str] = None,
    permission: Optional[str] = None
) -> None:
    """Log successful permission check for audit purposes.
    
    Args:
        claims: JWT claims of the user.
        endpoint: Endpoint path that was accessed.
        role: Role that granted access.
        permission: Permission that granted access.
    """
    # Only log in debug mode to avoid log spam
    logger.debug(
        f"RBAC_PERMISSION_GRANTED: "
        f"user_id={claims.user_id}, "
        f"tenant_id={claims.tenant_id}, "
        f"endpoint={endpoint}, "
        f"role={role}, "
        f"permission={permission}"
    )
