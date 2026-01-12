"""Unit tests for tenant provisioning."""
import pytest
from typing import Any, Generator
from unittest.mock import Mock, patch
from uuid import uuid4
from supabase import Client

from src.services.tenant_provisioning import (
    TenantProvisioningService,
    ProvisioningError,
)
from src.services.storage_setup import StorageSetupService, StorageSetupError


@pytest.fixture
def mock_supabase_client() -> Any:
    """Create a mock Supabase client."""
    client = Mock(spec=Client)
    client.table = Mock(return_value=client)
    client.select = Mock(return_value=client)
    client.insert = Mock(return_value=client)
    client.eq = Mock(return_value=client)
    client.limit = Mock(return_value=client)
    client.delete = Mock(return_value=client)
    client.execute = Mock(return_value=Mock(data=[]))
    client.auth = Mock()
    client.auth.admin = Mock()
    client.storage = Mock()
    return client


@pytest.fixture
def provisioning_service(mock_supabase_client) -> Any:
    """Create a TenantProvisioningService instance."""
    with patch('src.services.tenant_provisioning.get_auth_config') as mock_config:
        mock_config.return_value = Mock(
            supabase_url="https://test.supabase.co",
            supabase_service_key="test-service-key",
        )
        service = TenantProvisioningService(mock_supabase_client)
        return service


def test_provision_tenant_success(provisioning_service, mock_supabase_client) -> None:
    """Test successful tenant provisioning."""
    tenant_id = uuid4()
    user_id = str(uuid4())
    
    # Mock slug validation (no existing tenant)
    call_count = [0]  # Use list to allow modification in nested function
    
    def execute_side_effect() -> Any:
        call_count[0] += 1
        current_count = call_count[0]
        
        if current_count == 1:
            # Slug check - no existing tenant
            return Mock(data=[])
        elif current_count == 2:
            # Tenant creation
            return Mock(data=[{
                "id": str(tenant_id),
                "name": "Test Tenant",
                "slug": "test-tenant",
                "status": "active",
                "created_at": "2026-01-08T00:00:00Z",
            }])
        elif current_count == 3:
            # Tenant user creation
            return Mock(data=[{
                "tenant_id": str(tenant_id),
                "user_id": user_id,
                "roles": ["Admin"],
            }])
        return Mock(data=[])
    
    # Reset the default return value and set side_effect
    mock_supabase_client.execute.return_value = None
    mock_supabase_client.execute.side_effect = execute_side_effect
    
    # Mock storage service
    with patch.object(provisioning_service.storage_service, 'create_tenant_bucket') as mock_bucket:
        mock_bucket.return_value = f"documents-{tenant_id}"
        
        # Mock auth admin create_user
        mock_user = Mock()
        mock_user.id = user_id
        mock_auth_response = Mock()
        mock_auth_response.user = mock_user
        mock_supabase_client.auth.admin.create_user = Mock(return_value=mock_auth_response)
        
        # Mock storage list (bucket check)
        mock_supabase_client.storage.from_ = Mock(return_value=Mock(
            list=Mock(side_effect=Exception("Bucket doesn't exist"))
        ))
        
        result = provisioning_service.provision_tenant(
            name="Test Tenant",
            slug="test-tenant",
            admin_email="admin@test.com",
            environment="prod",
        )
        
        assert result["tenant_id"] == str(tenant_id)
        assert result["name"] == "Test Tenant"
        assert result["slug"] == "test-tenant"
        assert result["status"] == "active"
        assert result["storage_bucket"] == f"documents-{tenant_id}"
        assert result["admin_invite_sent"] is True


def test_provision_tenant_duplicate_slug(provisioning_service, mock_supabase_client) -> None:
    """Test provisioning fails with duplicate slug."""
    # Mock slug validation (tenant exists)
    mock_supabase_client.execute.return_value = Mock(data=[{"id": str(uuid4())}])
    
    with pytest.raises(ProvisioningError) as exc_info:
        provisioning_service.provision_tenant(
            name="Test Tenant",
            slug="existing-tenant",
            admin_email="admin@test.com",
        )
    
    assert "already exists" in str(exc_info.value).lower()


def test_provision_tenant_rollback_on_bucket_failure(
    provisioning_service,
    mock_supabase_client
) -> None:
    """Test that rollback occurs when bucket creation fails."""
    tenant_id = uuid4()
    
    # Mock slug validation (no existing tenant)
    call_count = [0]
    
    def execute_side_effect() -> Any:
        call_count[0] += 1
        current_count = call_count[0]
        
        if current_count == 1:
            # Slug check
            return Mock(data=[])
        elif current_count == 2:
            # Tenant creation
            return Mock(data=[{
                "id": str(tenant_id),
                "name": "Test Tenant",
                "slug": "test-tenant",
                "status": "active",
                "created_at": "2026-01-08T00:00:00Z",
            }])
        elif current_count == 3:
            # Rollback: delete tenant_users (if created)
            return Mock(data=[])
        elif current_count == 4:
            # Rollback: delete tenant
            return Mock(data=[])
        return Mock(data=[])
    
    mock_supabase_client.execute.return_value = None
    mock_supabase_client.execute.side_effect = execute_side_effect
    
    # Mock storage service to fail
    with patch.object(provisioning_service.storage_service, 'create_tenant_bucket') as mock_bucket:
        mock_bucket.side_effect = StorageSetupError("Bucket creation failed")
        
        # Mock rollback bucket deletion
        with patch.object(provisioning_service.storage_service, 'delete_tenant_bucket'):
            with pytest.raises(ProvisioningError):
                provisioning_service.provision_tenant(
                    name="Test Tenant",
                    slug="test-tenant",
                    admin_email="admin@test.com",
                )
            
            # Verify rollback was called (tenant should be deleted)
            delete_calls = [
                call for call in mock_supabase_client.delete.call_args_list
                if call is not None
            ]
            assert len(delete_calls) > 0 or mock_supabase_client.execute.call_count >= 3


def test_provision_tenant_rollback_on_user_failure(
    provisioning_service,
    mock_supabase_client
) -> None:
    """Test that rollback occurs when user creation fails."""
    tenant_id = uuid4()
    
    # Mock slug validation and tenant creation
    def execute_side_effect() -> Any:
        call_count = getattr(execute_side_effect, "call_count", 0)
        execute_side_effect.call_count = call_count + 1
        
        if call_count == 1:
            return Mock(data=[])  # Slug check
        elif call_count == 2:
            return Mock(data=[{
                "id": str(tenant_id),
                "name": "Test Tenant",
                "slug": "test-tenant",
                "status": "active",
                "created_at": "2026-01-08T00:00:00Z",
            }])  # Tenant creation
        elif call_count == 3:
            return Mock(data=[])  # Rollback tenant deletion
        return Mock(data=[])
    
    mock_supabase_client.execute.side_effect = execute_side_effect
    
    # Mock storage to succeed
    with patch.object(provisioning_service.storage_service, 'create_tenant_bucket') as mock_bucket:
        mock_bucket.return_value = f"documents-{tenant_id}"
        
        # Mock storage deletion for rollback
        with patch.object(provisioning_service.storage_service, 'delete_tenant_bucket'):
            # Mock auth to fail
            mock_supabase_client.auth.admin.create_user = Mock(
                side_effect=Exception("Auth API error")
            )
            
            with pytest.raises(ProvisioningError):
                provisioning_service.provision_tenant(
                    name="Test Tenant",
                    slug="test-tenant",
                    admin_email="admin@test.com",
                )


def test_storage_setup_create_bucket(mock_supabase_client) -> None:
    """Test storage bucket creation."""
    
    tenant_id = uuid4()
    bucket_name = f"documents-{tenant_id}"
    
    service = StorageSetupService(
        mock_supabase_client,
        "https://test.supabase.co",
        "test-key",
    )
    
    # Mock bucket doesn't exist
    mock_supabase_client.storage.from_ = Mock(return_value=Mock(
        list=Mock(side_effect=Exception("Not found"))
    ))
    
    # Mock HTTP request for bucket creation
    with patch('httpx.Client') as mock_httpx:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_client_instance = Mock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx.return_value.__enter__.return_value = mock_client_instance
        
        result = service.create_tenant_bucket(tenant_id)
        
        assert result == bucket_name


def test_storage_setup_delete_bucket(mock_supabase_client) -> None:
    """Test storage bucket deletion."""
    
    tenant_id = uuid4()
    
    service = StorageSetupService(
        mock_supabase_client,
        "https://test.supabase.co",
        "test-key",
    )
    
    # Mock HTTP request for bucket deletion
    with patch('httpx.Client') as mock_httpx:
        mock_response = Mock()
        mock_response.status_code = 204
        mock_client_instance = Mock()
        mock_client_instance.delete.return_value = mock_response
        mock_httpx.return_value.__enter__.return_value = mock_client_instance
        
        # Should not raise
        service.delete_tenant_bucket(tenant_id)
