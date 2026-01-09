"""Supabase Storage bucket setup for tenant isolation."""
from uuid import UUID
from supabase import Client
import logging
import httpx

logger = logging.getLogger(__name__)


class StorageSetupError(Exception):
    """Error during storage bucket setup."""
    pass


class StorageSetupService:
    """Service for creating and configuring tenant storage buckets."""
    
    # Allowed MIME types for tenant documents
    ALLOWED_MIME_TYPES = [
        "application/pdf",
        "image/*",
        "text/*",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]
    
    MAX_FILE_SIZE = 104857600  # 100 MB
    
    def __init__(self, supabase_client: Client, supabase_url: str, supabase_service_key: str):
        """
        Initialize storage setup service.
        
        Args:
            supabase_client: Supabase client with service_role key
            supabase_url: Supabase project URL
            supabase_service_key: Supabase service role key
        """
        self.client = supabase_client
        self.supabase_url = supabase_url.rstrip('/')
        self.service_key = supabase_service_key
    
    def create_tenant_bucket(self, tenant_id: UUID) -> str:
        """
        Create a storage bucket for a tenant.
        
        Args:
            tenant_id: Tenant UUID
            
        Returns:
            Bucket name (documents-{tenant_id})
            
        Raises:
            StorageSetupError: If bucket creation fails
        """
        bucket_name = f"documents-{tenant_id}"
        
        try:
            # Check if bucket already exists
            try:
                # Try to list files in bucket (will fail if bucket doesn't exist)
                self.client.storage.from_(bucket_name).list()
                logger.info(f"Bucket {bucket_name} already exists")
                return bucket_name
            except Exception:
                # Bucket doesn't exist, create it
                pass
            
            # Create bucket via Supabase Storage Management API
            # Using HTTP request directly as Python client doesn't have bucket creation
            # Ensure URL has proper format (no double slashes)
            base_url = self.supabase_url.rstrip('/')
            url = f"{base_url}/storage/v1/bucket"
            headers = {
                "Authorization": f"Bearer {self.service_key}",
                "apikey": self.service_key,
                "Content-Type": "application/json",
            }
            # Simplified payload - some fields may not be supported via API
            # Bucket settings can be configured via Dashboard after creation
            payload = {
                "name": bucket_name,
                "public": False,
            }
            
            with httpx.Client() as http_client:
                response = http_client.post(url, json=payload, headers=headers, timeout=30.0)
                
                if response.status_code == 200:
                    logger.info(f"Created storage bucket: {bucket_name}")
                    return bucket_name
                elif response.status_code == 409:
                    # Bucket already exists
                    logger.info(f"Bucket {bucket_name} already exists")
                    return bucket_name
                else:
                    error_msg = response.text
                    logger.error(f"Failed to create bucket: {response.status_code} - {error_msg}")
                    raise StorageSetupError(f"Failed to create storage bucket: {error_msg}")
                
        except StorageSetupError:
            raise
        except Exception as e:
            logger.error(f"Error creating bucket {bucket_name}: {e}")
            raise StorageSetupError(f"Failed to create storage bucket: {str(e)}")
    
    def setup_bucket_policies(self, tenant_id: UUID, bucket_name: str) -> None:
        """
        Set up RLS policies for tenant bucket access.
        
        Note: Storage bucket policies are set via SQL migration.
        This method documents the expected policy.
        
        Args:
            tenant_id: Tenant UUID
            bucket_name: Name of the bucket
            
        Raises:
            StorageSetupError: If policy setup fails
        """
        try:
            # Storage bucket policies are set via SQL migration
            # The policy should be:
            # - Users can only access buckets matching their tenant_id
            # - Policy: bucket_id = 'documents-' || auth.tenant_id()::text
            
            logger.info(f"Bucket policies for {bucket_name} should be set via migration")
            logger.info("Expected policy: bucket_id = 'documents-' || auth.tenant_id()::text")
            
            # Policies are typically created via migration, not programmatically
            # This is a no-op for now - policies should be in migration
            
        except Exception as e:
            logger.error(f"Error setting up bucket policies: {e}")
            raise StorageSetupError(f"Failed to setup bucket policies: {str(e)}")
    
    def delete_tenant_bucket(self, tenant_id: UUID) -> None:
        """
        Delete a tenant's storage bucket (for rollback).
        
        Args:
            tenant_id: Tenant UUID
            
        Raises:
            StorageSetupError: If deletion fails
        """
        bucket_name = f"documents-{tenant_id}"
        
        try:
            # Delete bucket via Supabase Storage Management API
            base_url = self.supabase_url.rstrip('/')
            url = f"{base_url}/storage/v1/bucket/{bucket_name}"
            headers = {
                "Authorization": f"Bearer {self.service_key}",
                "apikey": self.service_key,
            }
            
            with httpx.Client() as http_client:
                response = http_client.delete(url, headers=headers, timeout=30.0)
                
                if response.status_code in (200, 204):
                    logger.info(f"Deleted storage bucket: {bucket_name}")
                elif response.status_code == 404:
                    logger.warning(f"Bucket {bucket_name} not found (may already be deleted)")
                else:
                    logger.warning(f"Could not delete bucket {bucket_name}: {response.status_code}")
                    
        except Exception as e:
            logger.warning(f"Error deleting bucket {bucket_name}: {e} (may not exist)")
            # Don't raise - bucket might not exist or already deleted
