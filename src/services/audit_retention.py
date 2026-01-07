"""Service for managing tenant-specific audit retention configuration."""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..db.connection import get_connection_manager
from ..config.audit_config import get_audit_config

logger = logging.getLogger(__name__)


def get_tenant_retention_years(tenant_id: str) -> int:
    """Get retention period in years for a specific tenant.
    
    Args:
        tenant_id: Tenant identifier (UUID string).
    
    Returns:
        Retention period in years (defaults to system default if not configured).
    """
    config = get_audit_config()
    default_retention = config.audit_retention_years
    
    try:
        connection_manager = get_connection_manager()
        with connection_manager.get_session() as session:
            config_key = f"tenant_retention:{tenant_id}"
            
            result = session.execute(
                text("""
                    SELECT CAST(value::text AS INTEGER)
                    FROM control_plane.system_config
                    WHERE key = :key
                """),
                {"key": config_key}
            ).scalar()
            
            if result is not None:
                retention_years = int(result)
                logger.debug(
                    f"Retrieved tenant-specific retention: "
                    f"tenant_id={tenant_id}, retention_years={retention_years}"
                )
                return retention_years
            
            logger.debug(
                f"No tenant-specific retention found for {tenant_id}, "
                f"using default: {default_retention} years"
            )
            return default_retention
            
    except Exception as e:
        logger.error(
            f"Error retrieving tenant retention for {tenant_id}: {e}",
            exc_info=True
        )
        return default_retention


def set_tenant_retention_years(tenant_id: str, retention_years: int) -> bool:
    """Set retention period in years for a specific tenant.
    
    Args:
        tenant_id: Tenant identifier (UUID string).
        retention_years: Retention period in years (must be >= 1 and <= 30).
    
    Returns:
        True if successful, False otherwise.
    
    Raises:
        ValueError: If retention_years is out of valid range.
    """
    if retention_years < 1 or retention_years > 30:
        raise ValueError(
            f"Retention years must be between 1 and 30, got: {retention_years}"
        )
    
    try:
        connection_manager = get_connection_manager()
        with connection_manager.get_session() as session:
            config_key = f"tenant_retention:{tenant_id}"
            
            session.execute(
                text("""
                    INSERT INTO control_plane.system_config (key, value)
                    VALUES (:key, CAST(:value AS jsonb))
                    ON CONFLICT (key) 
                    DO UPDATE SET 
                        value = CAST(:value AS jsonb),
                        updated_at = CURRENT_TIMESTAMP
                """),
                {"key": config_key, "value": str(retention_years)}
            )
            
            session.commit()
            
            logger.info(
                f"Set tenant retention: tenant_id={tenant_id}, "
                f"retention_years={retention_years}"
            )
            return True
            
    except Exception as e:
        logger.error(
            f"Error setting tenant retention for {tenant_id}: {e}",
            exc_info=True
        )
        return False
