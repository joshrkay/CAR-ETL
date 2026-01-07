"""Tenant database connection resolver with caching."""
import logging
import time
import uuid
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.db.connection import get_connection_manager
from src.db.models.control_plane import Tenant, TenantDatabase, TenantStatus, DatabaseStatus
from src.services.encryption import EncryptionService, get_encryption_service

logger = logging.getLogger(__name__)

# Cache TTL: 5 minutes
CACHE_TTL_SECONDS = 300


@dataclass
class TenantConnection:
    """Cached tenant database connection information."""
    
    tenant_id: str
    connection_string: str
    engine: Engine
    cached_at: float
    expires_at: float
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() > self.expires_at


class TenantResolver:
    """Resolves tenant database connections with caching."""
    
    def __init__(
        self,
        encryption_service: Optional[EncryptionService] = None,
        cache_ttl: int = CACHE_TTL_SECONDS
    ):
        """Initialize tenant resolver.
        
        Args:
            encryption_service: Encryption service for decrypting connection strings.
            cache_ttl: Cache TTL in seconds (default: 5 minutes).
        """
        self.encryption_service = encryption_service or get_encryption_service()
        self.connection_manager = get_connection_manager()
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, TenantConnection] = {}
    
    def _validate_tenant_id_format(self, tenant_id: str) -> Optional[uuid.UUID]:
        """Validate tenant_id is a valid UUID format.
        
        Args:
            tenant_id: Tenant identifier string.
        
        Returns:
            UUID object if valid, None otherwise.
        """
        try:
            return uuid.UUID(tenant_id)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid tenant_id format (not UUID): {tenant_id}, error: {e}")
            return None
    
    def _get_tenant_from_db(self, tenant_id: str) -> Optional[Tuple[Tenant, TenantDatabase]]:
        """Get tenant and database records from control plane.
        
        Args:
            tenant_id: Tenant identifier (UUID string).
        
        Returns:
            Tuple of (Tenant, TenantDatabase) or None if not found.
        """
        try:
            # Validate UUID format first
            tenant_uuid = self._validate_tenant_id_format(tenant_id)
            if not tenant_uuid:
                return None
            
            with self.connection_manager.get_session() as session:
                
                # Get tenant
                tenant = session.query(Tenant).filter_by(tenant_id=tenant_uuid).first()
                if not tenant:
                    logger.warning(f"Tenant not found: {tenant_id}")
                    return None
                
                # Get active database for tenant
                tenant_db = session.query(TenantDatabase).filter_by(
                    tenant_id=tenant_uuid,
                    status=DatabaseStatus.ACTIVE
                ).first()
                
                if not tenant_db:
                    logger.warning(f"No active database found for tenant: {tenant_id}")
                    return None
                
                return (tenant, tenant_db)
        except Exception as e:
            logger.error(f"Error fetching tenant from database: {e}", exc_info=True)
            return None
    
    def _decrypt_connection_string(self, encrypted_string: str) -> Optional[str]:
        """Decrypt connection string.
        
        Args:
            encrypted_string: Encrypted connection string.
        
        Returns:
            Decrypted connection string or None if decryption fails.
        """
        try:
            return self.encryption_service.decrypt(encrypted_string)
        except Exception as e:
            logger.error(f"Failed to decrypt connection string: {e}")
            return None
    
    def _create_engine(self, connection_string: str) -> Engine:
        """Create SQLAlchemy engine from connection string.
        
        Args:
            connection_string: PostgreSQL connection string.
        
        Returns:
            SQLAlchemy engine.
        """
        # Add SSL mode if using Supabase
        connect_args = {}
        if "supabase" in connection_string.lower() and "sslmode" not in connection_string:
            if "?" in connection_string:
                connection_string += "&sslmode=require"
            else:
                connection_string += "?sslmode=require"
        
        return create_engine(
            connection_string,
            pool_pre_ping=True,  # Verify connections before using
            echo=False,
            future=True,
            connect_args=connect_args
        )
    
    def _validate_tenant_status(self, tenant: Tenant) -> bool:
        """Validate tenant is active.
        
        Args:
            tenant: Tenant record.
        
        Returns:
            True if tenant is active, False otherwise.
        """
        if tenant.status != TenantStatus.ACTIVE:
            logger.warning(
                f"Tenant {tenant.tenant_id} is not active: status={tenant.status.value}"
            )
            return False
        return True
    
    def resolve_tenant_connection(self, tenant_id: str) -> Optional[Engine]:
        """Resolve tenant database connection with caching.
        
        Args:
            tenant_id: Tenant identifier (UUID string).
        
        Returns:
            SQLAlchemy engine for tenant database, or None if resolution fails.
        """
        # Check cache first
        cached = self._cache.get(tenant_id)
        if cached and not cached.is_expired():
            logger.debug(f"Cache hit for tenant: {tenant_id}")
            return cached.engine
        
        # Cache miss or expired - resolve from database
        logger.info(f"Resolving tenant connection: tenant_id={tenant_id}")
        start_time = time.time()
        
        # Get tenant and database records
        result = self._get_tenant_from_db(tenant_id)
        if not result:
            return None
        
        tenant, tenant_db = result
        
        # Validate tenant status
        if not self._validate_tenant_status(tenant):
            return None
        
        # Decrypt connection string
        connection_string = self._decrypt_connection_string(
            tenant_db.connection_string_encrypted
        )
        if not connection_string:
            logger.error(f"Failed to decrypt connection string for tenant: {tenant_id}")
            return None
        
        # Create engine
        try:
            engine = self._create_engine(connection_string)
            
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            logger.error(f"Failed to create or test connection for tenant {tenant_id}: {e}")
            return None
        
        # Cache the connection
        now = time.time()
        cached_connection = TenantConnection(
            tenant_id=tenant_id,
            connection_string=connection_string,
            engine=engine,
            cached_at=now,
            expires_at=now + self.cache_ttl
        )
        self._cache[tenant_id] = cached_connection
        
        elapsed = (time.time() - start_time) * 1000  # Convert to milliseconds
        logger.info(
            f"Tenant connection resolved: tenant_id={tenant_id}, "
            f"elapsed={elapsed:.2f}ms"
        )
        
        return engine
    
    def invalidate_cache(self, tenant_id: Optional[str] = None) -> None:
        """Invalidate cache entry(s).
        
        Args:
            tenant_id: Specific tenant ID to invalidate, or None to clear all cache.
        """
        if tenant_id:
            if tenant_id in self._cache:
                del self._cache[tenant_id]
                logger.info(f"Cache invalidated for tenant: {tenant_id}")
        else:
            self._cache.clear()
            logger.info("All tenant cache invalidated")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics.
        """
        now = time.time()
        active_entries = sum(
            1 for conn in self._cache.values()
            if not conn.is_expired()
        )
        
        return {
            "total_entries": len(self._cache),
            "active_entries": active_entries,
            "expired_entries": len(self._cache) - active_entries
        }


def get_tenant_resolver() -> TenantResolver:
    """Get or create tenant resolver instance."""
    return TenantResolver()
