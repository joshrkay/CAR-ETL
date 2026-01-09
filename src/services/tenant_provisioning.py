"""Tenant provisioning service with rollback support."""
from uuid import UUID
from typing import Optional
import logging
from supabase import Client

from src.services.storage_setup import StorageSetupService, StorageSetupError
from src.auth.config import get_auth_config
from src.utils.pii_protection import hash_email

logger = logging.getLogger(__name__)


class ProvisioningError(Exception):
    """Error during tenant provisioning."""
    pass


class TenantProvisioningService:
    """Service for provisioning new tenants with storage and admin user."""
    
    def __init__(self, supabase_client: Client):
        """
        Initialize tenant provisioning service.
        
        Args:
            supabase_client: Supabase client with service_role key
        """
        self.client = supabase_client
        config = get_auth_config()
        self.storage_service = StorageSetupService(
            supabase_client,
            config.supabase_url,
            config.supabase_service_key,
        )
    
    def provision_tenant(
        self,
        name: str,
        slug: str,
        admin_email: str,
        environment: str = "prod",
    ) -> dict:
        """
        Provision a new tenant with storage bucket and admin user.
        
        Args:
            name: Tenant name
            slug: Tenant slug (URL-safe, unique)
            admin_email: Email for admin user
            environment: Environment (prod, staging, dev)
            
        Returns:
            Dictionary with tenant details
            
        Raises:
            ProvisioningError: If provisioning fails (with rollback)
        """
        tenant_id: Optional[UUID] = None
        user_id: Optional[str] = None
        bucket_created = False
        
        try:
            # Step 1: Validate slug uniqueness
            logger.info(f"Validating slug uniqueness: {slug}")
            existing = (
                self.client.table("tenants")
                .select("id")
                .eq("slug", slug)
                .limit(1)
                .execute()
            )
            
            if existing.data:
                raise ProvisioningError(f"Tenant with slug '{slug}' already exists")
            
            # Step 2: Create tenant row
            logger.info(f"Creating tenant: {name} ({slug})")
            tenant_result = (
                self.client.table("tenants")
                .insert({
                    "name": name,
                    "slug": slug,
                    "environment": environment,
                    "status": "active",
                })
                .execute()
            )
            
            if not tenant_result.data:
                raise ProvisioningError("Failed to create tenant")
            
            tenant_id = UUID(str(tenant_result.data[0]["id"]))
            logger.info(f"Created tenant: {tenant_id}")
            
            # Step 3: Create storage bucket
            logger.info(f"Creating storage bucket for tenant {tenant_id}")
            try:
                bucket_name = self.storage_service.create_tenant_bucket(tenant_id)
                bucket_created = True
                logger.info(f"Created storage bucket: {bucket_name}")
            except StorageSetupError as e:
                raise ProvisioningError(f"Failed to create storage bucket: {str(e)}")
            
            # Step 4: Setup bucket policies (documented, actual setup via migration)
            logger.info("Bucket policies should be set via migration")
            self.storage_service.setup_bucket_policies(tenant_id, bucket_name)
            
            # Step 5: Invite admin user via Supabase Auth
            logger.info(f"Inviting admin user: {admin_email}")
            try:
                # Try to create user (will fail if exists, which is okay)
                try:
                    auth_response = self.client.auth.admin.create_user({
                        "email": admin_email,
                        "email_confirm": True,
                        "user_metadata": {
                            "tenant_id": str(tenant_id),
                        },
                    })
                    user_id = auth_response.user.id
                    logger.info(f"Created admin user: {user_id}")
                except Exception as create_error:
                    # User might already exist, check error message
                    error_str = str(create_error).lower()
                    error_type = type(create_error).__name__
                    
                    if "already" in error_str or "exists" in error_str or "duplicate" in error_str:
                        logger.info(
                            f"User {admin_email} already exists, will link to tenant",
                            extra={
                                "tenant_id": str(tenant_id),
                                "admin_email": hash_email(admin_email),
                                "error_type": error_type,
                            },
                        )
                        raise ProvisioningError(
                            f"User {admin_email} already exists. "
                            "Use invite_user API or provide user_id for existing users."
                        ) from create_error
                    else:
                        logger.error(
                            "Failed to create admin user",
                            extra={
                                "tenant_id": str(tenant_id),
                                "admin_email": hash_email(admin_email),
                                "error": str(create_error),
                                "error_type": error_type,
                            },
                            exc_info=True,
                        )
                        raise ProvisioningError(
                            f"Failed to create admin user: {str(create_error)}"
                        ) from create_error
                
            except ProvisioningError:
                raise
            except Exception as e:
                logger.error(
                    "Unexpected error creating/inviting admin user",
                    extra={
                        "tenant_id": str(tenant_id),
                        "admin_email": hash_email(admin_email),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
                raise ProvisioningError(f"Failed to create admin user: {str(e)}") from e
            
            # Step 6: Create tenant_users row linking admin
            logger.info("Linking admin user to tenant")
            try:
                tenant_user_result = (
                    self.client.table("tenant_users")
                    .insert({
                        "tenant_id": str(tenant_id),
                        "user_id": user_id,
                        "roles": ["Admin"],
                    })
                    .execute()
                )
                
                if not tenant_user_result.data:
                    raise ProvisioningError("Failed to link admin user to tenant")
                
                logger.info("Linked admin user to tenant")
                
            except ProvisioningError:
                raise
            except Exception as e:
                logger.error(
                    "Failed to link admin user to tenant",
                    extra={
                        "tenant_id": str(tenant_id),
                        "user_id": user_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
                raise ProvisioningError(f"Failed to link admin user: {str(e)}") from e
            
            # Step 7: Return success
            tenant_data = tenant_result.data[0]
            return {
                "tenant_id": str(tenant_id),
                "name": tenant_data["name"],
                "slug": tenant_data["slug"],
                "status": tenant_data["status"],
                "storage_bucket": bucket_name,
                "admin_invite_sent": True,
                "created_at": tenant_data["created_at"],
            }
            
        except ProvisioningError:
            # Rollback on failure
            logger.error(
                "Provisioning failed, rolling back",
                extra={
                    "tenant_id": str(tenant_id) if tenant_id else None,
                    "user_id": user_id,
                    "bucket_created": bucket_created,
                },
            )
            self._rollback(tenant_id, user_id, bucket_created)
            raise
        except Exception as e:
            # Unexpected error - rollback
            logger.error(
                "Unexpected error during provisioning",
                extra={
                    "tenant_id": str(tenant_id) if tenant_id else None,
                    "user_id": user_id,
                    "bucket_created": bucket_created,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            self._rollback(tenant_id, user_id, bucket_created)
            raise ProvisioningError(f"Unexpected error: {str(e)}") from e
    
    def _rollback(
        self,
        tenant_id: Optional[UUID],
        user_id: Optional[str],
        bucket_created: bool,
    ) -> None:
        """
        Rollback provisioning steps on failure.
        
        Args:
            tenant_id: Tenant ID to rollback (if created)
            user_id: User ID to rollback (if created)
            bucket_created: Whether bucket was created
        """
        logger.info("Starting rollback...")
        
        # Rollback in reverse order
        
        # 1. Delete tenant_users row (if created)
        if tenant_id and user_id:
            try:
                self.client.table("tenant_users").delete().eq(
                    "tenant_id", str(tenant_id)
                ).eq("user_id", user_id).execute()
                logger.info("Rolled back tenant_users row")
            except Exception as e:
                logger.warning(
                    "Failed to rollback tenant_users row",
                    extra={
                        "tenant_id": str(tenant_id),
                        "user_id": user_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
        
        # 2. Delete storage bucket (if created)
        if bucket_created and tenant_id:
            try:
                self.storage_service.delete_tenant_bucket(tenant_id)
                logger.info("Rolled back storage bucket")
            except StorageSetupError as e:
                logger.warning(
                    "Failed to rollback storage bucket",
                    extra={
                        "tenant_id": str(tenant_id),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
            except Exception as e:
                logger.warning(
                    "Unexpected error rolling back storage bucket",
                    extra={
                        "tenant_id": str(tenant_id),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
        
        # 3. Delete user (if created - be careful, might be existing user)
        # Note: We don't delete existing users, only ones we created
        # For now, we'll skip user deletion in rollback
        
        # 4. Delete tenant row (if created)
        if tenant_id:
            try:
                self.client.table("tenants").delete().eq("id", str(tenant_id)).execute()
                logger.info("Rolled back tenant row")
            except Exception as e:
                logger.warning(
                    "Failed to rollback tenant row",
                    extra={
                        "tenant_id": str(tenant_id),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
        
        logger.info("Rollback complete")
