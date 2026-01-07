"""High-level audit logging service."""
import asyncio
import logging
from typing import Optional, Dict, Any
from fastapi import Request

from .models import AuditLogEntry
from .logger_factory import get_audit_logger

logger = logging.getLogger(__name__)


async def audit_log(
    user_id: str,
    tenant_id: str,
    action_type: str,
    resource_id: Optional[str] = None,
    request: Optional[Request] = None,
    additional_metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Log an audit event asynchronously.
    
    Args:
        user_id: User ID who performed the action.
        tenant_id: Tenant ID where action occurred.
        action_type: Type of action (e.g., "document.upload", "user.delete").
        resource_id: Optional ID of the resource affected.
        request: Optional FastAPI Request object to extract metadata.
        additional_metadata: Optional additional metadata to include.
    
    Example:
        await audit_log(
            user_id="auth0|123",
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            action_type="document.upload",
            resource_id="doc-456",
            request=request
        )
    """
    try:
        # Build request metadata
        request_metadata: Dict[str, Any] = {}
        
        if request:
            request_metadata.update({
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "client_host": request.client.host if request.client else None,
            })
            
            # Extract user agent if available
            user_agent = request.headers.get("user-agent")
            if user_agent:
                request_metadata["user_agent"] = user_agent
        
        if additional_metadata:
            request_metadata.update(additional_metadata)
        
        # Create audit entry
        entry = AuditLogEntry.create(
            user_id=user_id,
            tenant_id=tenant_id,
            action_type=action_type,
            resource_id=resource_id,
            request_metadata=request_metadata
        )
        
        # Queue for async write
        audit_logger = get_audit_logger()
        await audit_logger.log(entry)
        
    except Exception as e:
        # Never fail the main request due to audit logging errors
        logger.error(
            f"Failed to log audit event: user_id={user_id}, "
            f"action_type={action_type}, error={e}",
            exc_info=True
        )


def audit_log_sync(
    user_id: str,
    tenant_id: str,
    action_type: str,
    resource_id: Optional[str] = None,
    additional_metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Synchronously log a critical audit event (e.g., tampering attempt).
    
    Args:
        user_id: User ID who performed the action.
        tenant_id: Tenant ID where action occurred.
        action_type: Type of action.
        resource_id: Optional ID of the resource affected.
        additional_metadata: Optional additional metadata.
    
    Note:
        Use this only for critical events that must be logged immediately.
    """
    try:
        entry = AuditLogEntry.create(
            user_id=user_id,
            tenant_id=tenant_id,
            action_type=action_type,
            resource_id=resource_id,
            request_metadata=additional_metadata or {}
        )
        
        audit_logger = get_audit_logger()
        audit_logger.log_sync(entry)
        
    except Exception as e:
        logger.error(
            f"Failed to sync log audit event: user_id={user_id}, "
            f"action_type={action_type}, error={e}",
            exc_info=True
        )
