"""Integration tests for tenant provisioning with rollback scenarios."""
import os
import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.services.tenant_provisioning import TenantProvisioningService
from src.services.encryption import EncryptionService
from src.db.tenant_manager import TenantDatabaseManager
from src.api.routes.tenants import router
from src.db.connection import get_connection_manager


# Test app setup
app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture
def mock_encryption_service():
    """Mock encryption service."""
    service = Mock(spec=EncryptionService)
    service.encrypt = Mock(return_value="encrypted_connection_string")
    service.decrypt = Mock(return_value="postgresql://user:pass@host:5432/db")
    return service


@pytest.fixture
def mock_db_manager():
    """Mock database manager."""
    manager = Mock(spec=TenantDatabaseManager)
    manager.create_database = Mock(return_value=True)
    manager.delete_database = Mock(return_value=True)
    manager.test_connection = Mock(return_value=(True, None))
    manager.database_exists = Mock(return_value=False)
    return manager


@pytest.fixture
def provisioning_service(mock_db_manager, mock_encryption_service):
    """Create provisioning service with mocks."""
    return TenantProvisioningService(
        db_manager=mock_db_manager,
        encryption_service=mock_encryption_service
    )


class TestTenantProvisioning:
    """Test tenant provisioning functionality."""
    
    def test_provision_tenant_success(self, provisioning_service, mock_db_manager, mock_encryption_service):
        """Test successful tenant provisioning."""
        # Mock database session
        with patch('src.services.tenant_provisioning.get_connection_manager') as mock_cm:
            mock_session = MagicMock()
            mock_cm.return_value.get_session.return_value.__enter__.return_value = mock_session
            mock_cm.return_value.get_session.return_value.__exit__.return_value = None
            
            # Mock query to return None (tenant doesn't exist)
            mock_session.query.return_value.filter_by.return_value.first.return_value = None
            
            result = provisioning_service.provision_tenant(
                name="test_tenant",
                environment="development"
            )
            
            assert "tenant_id" in result
            assert result["name"] == "test_tenant"
            assert result["status"] == "active"
            
            # Verify database was created
            mock_db_manager.create_database.assert_called_once()
            
            # Verify connection was tested
            mock_db_manager.test_connection.assert_called_once()
            
            # Verify encryption was used
            mock_encryption_service.encrypt.assert_called_once()
            
            # Verify tenant was added to session
            assert mock_session.add.call_count == 2  # Tenant + TenantDatabase
            mock_session.commit.assert_called_once()
    
    def test_provision_tenant_rollback_on_db_creation_failure(self, provisioning_service, mock_db_manager, mock_encryption_service):
        """Test rollback when database creation fails."""
        # Mock database creation failure
        mock_db_manager.create_database.side_effect = Exception("Database creation failed")
        
        with patch('src.services.tenant_provisioning.get_connection_manager'):
            with pytest.raises(RuntimeError, match="Tenant provisioning failed"):
                provisioning_service.provision_tenant(
                    name="test_tenant",
                    environment="development"
                )
            
            # Verify rollback: database should not be deleted (wasn't created)
            mock_db_manager.delete_database.assert_not_called()
    
    def test_provision_tenant_rollback_on_connection_test_failure(self, provisioning_service, mock_db_manager, mock_encryption_service):
        """Test rollback when connection test fails."""
        # Mock connection test failure
        mock_db_manager.test_connection.return_value = (False, "Connection failed")
        
        with patch('src.services.tenant_provisioning.get_connection_manager'):
            with pytest.raises(RuntimeError, match="Tenant provisioning failed"):
                provisioning_service.provision_tenant(
                    name="test_tenant",
                    environment="development"
                )
            
            # Verify rollback: database should be deleted
            mock_db_manager.delete_database.assert_called_once()
    
    def test_provision_tenant_rollback_on_tenant_insert_failure(self, provisioning_service, mock_db_manager, mock_encryption_service):
        """Test rollback when tenant record insertion fails."""
        with patch('src.services.tenant_provisioning.get_connection_manager') as mock_cm:
            mock_session = MagicMock()
            mock_cm.return_value.get_session.return_value.__enter__.return_value = mock_session
            mock_cm.return_value.get_session.return_value.__exit__.return_value = None
            
            # Mock query to return None (tenant doesn't exist)
            mock_session.query.return_value.filter_by.return_value.first.return_value = None
            
            # Mock commit failure
            mock_session.commit.side_effect = Exception("Database insert failed")
            
            with pytest.raises(RuntimeError, match="Tenant provisioning failed"):
                provisioning_service.provision_tenant(
                    name="test_tenant",
                    environment="development"
                )
            
            # Verify rollback: database should be deleted
            mock_db_manager.delete_database.assert_called_once()
    
    def test_provision_tenant_duplicate_name(self, provisioning_service, mock_db_manager, mock_encryption_service):
        """Test provisioning fails when tenant name already exists."""
        with patch('src.services.tenant_provisioning.get_connection_manager') as mock_cm:
            mock_session = MagicMock()
            mock_cm.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            # Mock query to return existing tenant
            existing_tenant = Mock()
            mock_session.query.return_value.filter_by.return_value.first.return_value = existing_tenant
            
            with pytest.raises(ValueError, match="already exists"):
                provisioning_service.provision_tenant(
                    name="existing_tenant",
                    environment="development"
                )
            
            # Verify database was not created
            mock_db_manager.create_database.assert_not_called()
    
    def test_provision_tenant_invalid_environment(self, provisioning_service):
        """Test provisioning fails with invalid environment."""
        with pytest.raises(ValueError, match="Invalid environment"):
            provisioning_service.provision_tenant(
                name="test_tenant",
                environment="invalid"
            )
    
    def test_provision_tenant_empty_name(self, provisioning_service):
        """Test provisioning fails with empty name."""
        with pytest.raises(ValueError, match="Tenant name is required"):
            provisioning_service.provision_tenant(
                name="",
                environment="development"
            )


class TestTenantAPI:
    """Test tenant provisioning API endpoints."""
    
    def test_create_tenant_endpoint_success(self, mock_db_manager, mock_encryption_service):
        """Test successful tenant creation via API."""
        with patch('src.api.routes.tenants.get_tenant_provisioning_service') as mock_service:
            mock_provisioning = Mock()
            mock_provisioning.provision_tenant.return_value = {
                "tenant_id": str(uuid.uuid4()),
                "name": "test_tenant",
                "status": "active"
            }
            mock_service.return_value = mock_provisioning
            
            response = client.post(
                "/api/v1/tenants",
                json={
                    "name": "test_tenant",
                    "environment": "development"
                }
            )
            
            assert response.status_code == 201
            data = response.json()
            assert "tenant_id" in data
            assert data["name"] == "test_tenant"
            assert data["status"] == "active"
    
    def test_create_tenant_endpoint_validation_error(self):
        """Test API validation errors."""
        # Invalid environment
        response = client.post(
            "/api/v1/tenants",
            json={
                "name": "test_tenant",
                "environment": "invalid"
            }
        )
        assert response.status_code == 422
        
        # Empty name
        response = client.post(
            "/api/v1/tenants",
            json={
                "name": "",
                "environment": "development"
            }
        )
        assert response.status_code == 422
    
    def test_create_tenant_endpoint_duplicate_name(self):
        """Test API error when tenant name already exists."""
        with patch('src.api.routes.tenants.get_tenant_provisioning_service') as mock_service:
            mock_provisioning = Mock()
            mock_provisioning.provision_tenant.side_effect = ValueError("Tenant with name 'test' already exists")
            mock_service.return_value = mock_provisioning
            
            response = client.post(
                "/api/v1/tenants",
                json={
                    "name": "test",
                    "environment": "development"
                }
            )
            
            assert response.status_code == 400
            assert "already exists" in response.json()["detail"]
    
    def test_create_tenant_endpoint_provisioning_error(self):
        """Test API error when provisioning fails."""
        with patch('src.api.routes.tenants.get_tenant_provisioning_service') as mock_service:
            mock_provisioning = Mock()
            mock_provisioning.provision_tenant.side_effect = RuntimeError("Database creation failed")
            mock_service.return_value = mock_provisioning
            
            response = client.post(
                "/api/v1/tenants",
                json={
                    "name": "test_tenant",
                    "environment": "development"
                }
            )
            
            assert response.status_code == 500
            assert "provisioning failed" in response.json()["detail"].lower()


class TestRollbackScenarios:
    """Test various rollback scenarios."""
    
    def test_rollback_database_deleted_on_tenant_insert_failure(self, mock_db_manager, mock_encryption_service):
        """Verify database is deleted when tenant insert fails."""
        service = TenantProvisioningService(
            db_manager=mock_db_manager,
            encryption_service=mock_encryption_service
        )
        
        with patch('src.services.tenant_provisioning.get_connection_manager') as mock_cm:
            mock_session = MagicMock()
            mock_cm.return_value.get_session.return_value.__enter__.return_value = mock_session
            mock_cm.return_value.get_session.return_value.__exit__.return_value = None
            
            mock_session.query.return_value.filter_by.return_value.first.return_value = None
            mock_session.commit.side_effect = Exception("Insert failed")
            
            with pytest.raises(RuntimeError):
                service.provision_tenant("test", "development")
            
            # Verify database was deleted during rollback
            assert mock_db_manager.delete_database.called
    
    def test_rollback_tenant_deleted_on_database_creation_failure(self, mock_db_manager, mock_encryption_service):
        """Verify tenant record is deleted when database creation fails after insert."""
        service = TenantProvisioningService(
            db_manager=mock_db_manager,
            encryption_service=mock_encryption_service
        )
        
        # Simulate database creation success but later failure
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return True  # First call succeeds
            raise Exception("Database operation failed")
        
        mock_db_manager.create_database.side_effect = side_effect
        
        with patch('src.services.tenant_provisioning.get_connection_manager') as mock_cm:
            mock_session = MagicMock()
            mock_cm.return_value.get_session.return_value.__enter__.return_value = mock_session
            mock_cm.return_value.get_session.return_value.__exit__.return_value = None
            
            mock_session.query.return_value.filter_by.return_value.first.return_value = None
            
            with pytest.raises(RuntimeError):
                service.provision_tenant("test", "development")
            
            # Verify rollback attempts
            assert mock_db_manager.delete_database.called
