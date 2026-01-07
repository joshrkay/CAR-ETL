"""Factory for creating audit loggers based on configuration."""
import logging
from typing import Union, Any

from ..config.audit_config import get_audit_config

logger = logging.getLogger(__name__)


def get_audit_logger() -> Union[Any, Any]:
    """Get audit logger instance based on configuration.
    
    Returns:
        SupabaseAuditLogger or S3AuditLogger instance based on AUDIT_STORAGE_BACKEND.
    """
    config = get_audit_config()
    
    if config.audit_storage_backend == "supabase":
        from .supabase_logger import SupabaseAuditLogger
        return SupabaseAuditLogger()
    elif config.audit_storage_backend == "s3":
        from .s3_logger import S3AuditLogger
        if not config.audit_s3_bucket:
            raise ValueError(
                "AUDIT_S3_BUCKET is required when using S3 backend. "
                "Set AUDIT_STORAGE_BACKEND=supabase to use Supabase instead."
            )
        return S3AuditLogger()
    else:
        raise ValueError(
            f"Invalid AUDIT_STORAGE_BACKEND: {config.audit_storage_backend}. "
            "Must be 'supabase' or 's3'."
        )
