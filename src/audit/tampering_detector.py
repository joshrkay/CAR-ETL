"""Service for detecting and logging audit log tampering attempts."""
import logging
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError

from .models import AuditLogEntry
from .service import audit_log_sync

logger = logging.getLogger(__name__)


def detect_and_log_tampering_attempt(
    error: Exception,
    operation: str,
    s3_key: Optional[str] = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    additional_context: Optional[Dict[str, Any]] = None
) -> None:
    """Detect and log an audit log tampering attempt.
    
    Args:
        error: Exception that occurred (ClientError for S3 operations).
        operation: Operation that was attempted (e.g., "DeleteObject", "PutObject").
        s3_key: Optional S3 key that was targeted.
        tenant_id: Optional tenant ID (extracted from error if available).
        user_id: Optional user ID who attempted the operation.
        additional_context: Optional additional context about the attempt.
    """
    try:
        error_code = None
        error_message = str(error)
        
        if isinstance(error, ClientError):
            error_code = error.response.get('Error', {}).get('Code', '')
            error_message = error.response.get('Error', {}).get('Message', str(error))
        
        # Determine if this is a tampering attempt
        is_tampering = (
            error_code in [
                'InvalidObjectState',  # Object is locked
                'AccessDenied',  # Permission denied (may be tampering)
                'ObjectLockConfigurationNotFoundError'  # Lock config issue
            ] or
            'retention' in error_message.lower() or
            'lock' in error_message.lower()
        )
        
        if not is_tampering:
            return
        
        # Build metadata
        metadata: Dict[str, Any] = {
            "operation": operation,
            "error_code": error_code or "Unknown",
            "error_message": error_message,
            "is_tampering_attempt": True
        }
        
        if s3_key:
            metadata["s3_key"] = s3_key
        
        if additional_context:
            metadata.update(additional_context)
        
        # Log the tampering attempt synchronously (critical event)
        audit_log_sync(
            user_id=user_id or "system",
            tenant_id=tenant_id or "system",
            action_type="audit.tampering.attempt",
            resource_id=s3_key,
            additional_metadata=metadata
        )
        
        logger.warning(
            f"Audit log tampering attempt detected: "
            f"operation={operation}, error_code={error_code}, "
            f"s3_key={s3_key}, tenant_id={tenant_id}"
        )
        
    except Exception as e:
        # Never fail due to tampering detection errors
        logger.error(
            f"Error detecting tampering attempt: {e}",
            exc_info=True
        )


def wrap_s3_operation_with_tampering_detection(
    operation: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None
):
    """Decorator to wrap S3 operations and detect tampering attempts.
    
    Args:
        operation: Operation name (e.g., "DeleteObject").
        tenant_id: Optional tenant ID.
        user_id: Optional user ID.
    
    Returns:
        Decorator function.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                # Extract S3 key from kwargs if available
                s3_key = kwargs.get('Key') or kwargs.get('key')
                
                detect_and_log_tampering_attempt(
                    error=e,
                    operation=operation,
                    s3_key=s3_key,
                    tenant_id=tenant_id,
                    user_id=user_id
                )
                raise
        return wrapper
    return decorator
