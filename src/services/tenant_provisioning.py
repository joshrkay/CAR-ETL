"""Tenant provisioning service with rollback support."""
import logging
import uuid
from typing import Dict, Optional, Any
from datetime import datetime

from src.db.connection import get_connection_manager
from src.db.models.control_plane import Tenant, TenantDatabase, TenantEnvironment, TenantStatus, DatabaseStatus
from src.db.tenant_manager import TenantDatabaseManager
from src.services.encryption import EncryptionService

logger = logging.getLogger(__name__)


class TenantProvisioningService:
    """Service for provisioning new tenants with database creation."""
    
    def __init__(
        self,
        db_manager: Optional[TenantDatabaseManager] = None,
        encryption_service: Optional[EncryptionService] = None
    ):
        """Initialize tenant provisioning service.
        
        Args:
            db_manager: Tenant database manager instance.
            encryption_service: Encryption service instance.
        """
        self.db_manager = db_manager or TenantDatabaseManager()
        self.encryption_service = encryption_service or EncryptionService()
        self.connection_manager = get_connection_manager()
    
    def _validate_tenant_inputs(self, name: str, environment: str) -> None:
        """Validate tenant creation inputs.
        
        Args:
            name: Tenant name to validate.
            environment: Tenant environment to validate.
        
        Raises:
            ValueError: If validation fails.
        """
        if not name or not name.strip():
            raise ValueError("Tenant name is required")
        
        if environment not in ["development", "staging", "production"]:
            raise ValueError(
                f"Invalid environment: {environment}. "
                "Must be one of: development, staging, production"
            )
    
    def _build_connection_string(
        self,
        database_name: str,
        database_host: Optional[str] = None,
        database_port: int = 5432,
        database_user: Optional[str] = None,
        database_password: Optional[str] = None
    ) -> str:
        """Build PostgreSQL connection string.
        
        Args:
            database_name: Target database name.
            database_host: Database host (defaults to connection manager host).
            database_port: Database port (default: 5432).
            database_user: Database user (defaults to connection manager user).
            database_password: Database password (defaults to connection manager password).
        
        Returns:
            PostgreSQL connection string.
        """
        from urllib.parse import urlparse
        
        db_url = self.connection_manager.database_url
        parsed = urlparse(db_url)
        
        db_host = database_host or parsed.hostname or "localhost"
        db_port = database_port or parsed.port or 5432
        db_user = database_user or parsed.username or "postgres"
        db_password = database_password or (parsed.password if parsed.password else "")
        
        connection_string = (
            f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{database_name}"
        )
        
        # Add SSL mode if using Supabase
        if "supabase" in db_host.lower():
            connection_string += "?sslmode=require"
        
        return connection_string
    
    def _create_tenant_records(
        self,
        tenant_id: uuid.UUID,
        name: str,
        environment: str,
        database_name: str,
        encrypted_connection_string: str,
        db_host: str,
        db_port: int
    ) -> None:
        """Create tenant and tenant database records in control plane.
        
        Args:
            tenant_id: Unique tenant identifier.
            name: Tenant name.
            environment: Tenant environment.
            database_name: Tenant database name.
            encrypted_connection_string: Encrypted connection string.
            db_host: Database host.
            db_port: Database port.
        
        Raises:
            ValueError: If tenant name already exists.
            SQLAlchemyError: If database operation fails.
        """
        with self.connection_manager.get_session() as session:
            # Check if tenant name already exists
            existing = session.query(Tenant).filter_by(name=name).first()
            if existing:
                raise ValueError(f"Tenant with name '{name}' already exists")
            
            # Create tenant
            tenant = Tenant(
                tenant_id=tenant_id,
                name=name,
                environment=TenantEnvironment(environment),
                status=TenantStatus.ACTIVE,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(tenant)
            session.flush()  # Get tenant_id
            
            # Create tenant database record
            tenant_db = TenantDatabase(
                tenant_id=tenant_id,
                connection_string_encrypted=encrypted_connection_string,
                database_name=database_name,
                host=db_host,
                port=db_port,
                status=DatabaseStatus.ACTIVE,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(tenant_db)
            session.commit()
    
    def _rollback_provisioning(
        self,
        tenant_id: uuid.UUID,
        database_name: str,
        database_created: bool,
        tenant_record_created: bool
    ) -> None:
        """Rollback tenant provisioning on failure.
        
        Args:
            tenant_id: Tenant identifier to rollback.
            database_name: Database name to delete.
            database_created: Whether database was created.
            tenant_record_created: Whether tenant record was created.
        """
        # Rollback: Delete database if created
        if database_created:
            try:
                logger.info(f"Rolling back: deleting database {database_name}")
                self.db_manager.delete_database(database_name)
            except Exception as rollback_error:
                logger.error(f"Failed to delete database during rollback: {rollback_error}")
        
        # Rollback: Delete tenant record if created
        if tenant_record_created:
            try:
                logger.info(f"Rolling back: deleting tenant record {tenant_id}")
                with self.connection_manager.get_session() as session:
                    tenant = session.query(Tenant).filter_by(tenant_id=tenant_id).first()
                    if tenant:
                        session.delete(tenant)
                        session.commit()
            except Exception as rollback_error:
                logger.error(f"Failed to delete tenant record during rollback: {rollback_error}")
    
    def provision_tenant(
        self,
        name: str,
        environment: str,
        database_host: Optional[str] = None,
        database_port: int = 5432,
        database_user: Optional[str] = None,
        database_password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Provision a new tenant with isolated database.
        
        This method is atomic - if any step fails, all changes are rolled back.
        
        Args:
            name: Tenant name (must be unique).
            environment: Tenant environment (development, staging, production).
            database_host: Database host (defaults to connection manager host).
            database_port: Database port (default: 5432).
            database_user: Database user (defaults to connection manager user).
            database_password: Database password (defaults to connection manager password).
        
        Returns:
            Dictionary with tenant_id, name, and status.
        
        Raises:
            ValueError: If input validation fails.
            RuntimeError: If provisioning fails (with rollback).
        """
        # Validate inputs
        self._validate_tenant_inputs(name, environment)
        
        tenant_id = uuid.uuid4()
        database_name = f"car_{str(tenant_id).replace('-', '_')}"
        
        logger.info(f"Provisioning tenant: name={name}, environment={environment}, database={database_name}")
        
        # Track what needs rollback
        database_created = False
        tenant_record_created = False
        
        try:
            # Step 1: Create PostgreSQL database
            logger.info(f"Creating database: {database_name}")
            self.db_manager.create_database(database_name)
            database_created = True
            
            # Step 2: Build connection string
            connection_string = self._build_connection_string(
                database_name,
                database_host,
                database_port,
                database_user,
                database_password
            )
            
            # Step 3: Test database connection
            logger.info(f"Testing connection to {database_name}")
            connection_ok, error_msg = self.db_manager.test_connection(connection_string)
            
            if not connection_ok:
                raise RuntimeError(f"Database connection test failed: {error_msg}")
            
            # Step 4: Encrypt connection string
            logger.info("Encrypting connection string")
            encrypted_connection_string = self.encryption_service.encrypt(connection_string)
            
            # Step 5: Extract connection details for storage
            from urllib.parse import urlparse
            parsed = urlparse(connection_string)
            db_host = parsed.hostname or "localhost"
            db_port = parsed.port or 5432
            
            # Step 6: Create tenant record in control plane
            logger.info("Creating tenant record in control plane")
            self._create_tenant_records(
                tenant_id,
                name,
                environment,
                database_name,
                encrypted_connection_string,
                db_host,
                db_port
            )
            tenant_record_created = True
            
            logger.info(f"Tenant provisioned successfully: {tenant_id}")
            
            return {
                "tenant_id": str(tenant_id),
                "name": name,
                "status": "active"
            }
        
        except Exception as e:
            logger.error(f"Tenant provisioning failed: tenant_id={tenant_id}, error={type(e).__name__}")
            
            # Rollback all changes
            self._rollback_provisioning(tenant_id, database_name, database_created, tenant_record_created)
            
            # Re-raise the original error
            raise RuntimeError(f"Tenant provisioning failed: {e}") from e


def get_tenant_provisioning_service() -> TenantProvisioningService:
    """Get or create tenant provisioning service instance."""
    return TenantProvisioningService()
