"""Tests for tenant-specific audit retention configuration."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from src.services.audit_retention import (
    get_tenant_retention_years,
    set_tenant_retention_years
)


class TestAuditRetention:
    """Tests for audit retention service."""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = MagicMock(spec=Session)
        return session
    
    @pytest.fixture
    def mock_connection_manager(self, mock_session):
        """Create mock connection manager."""
        manager = Mock()
        manager.get_session.return_value.__enter__.return_value = mock_session
        manager.get_session.return_value.__exit__.return_value = None
        return manager
    
    def test_get_tenant_retention_default(self, mock_connection_manager, mock_session):
        """Test getting default retention when tenant-specific not configured."""
        mock_session.execute.return_value.scalar.return_value = None
        
        with patch(
            'src.services.audit_retention.get_connection_manager',
            return_value=mock_connection_manager
        ), patch(
            'src.services.audit_retention.get_audit_config'
        ) as mock_config:
            mock_config.return_value.audit_retention_years = 7
            
            retention = get_tenant_retention_years("test-tenant-id")
            
            assert retention == 7
            mock_session.execute.assert_called_once()
    
    def test_get_tenant_retention_custom(self, mock_connection_manager, mock_session):
        """Test getting tenant-specific retention."""
        mock_session.execute.return_value.scalar.return_value = 10
        
        with patch(
            'src.services.audit_retention.get_connection_manager',
            return_value=mock_connection_manager
        ):
            retention = get_tenant_retention_years("test-tenant-id")
            
            assert retention == 10
            mock_session.execute.assert_called_once()
    
    def test_set_tenant_retention_valid(self, mock_connection_manager, mock_session):
        """Test setting valid tenant retention."""
        with patch(
            'src.services.audit_retention.get_connection_manager',
            return_value=mock_connection_manager
        ):
            result = set_tenant_retention_years("test-tenant-id", 10)
            
            assert result is True
            mock_session.execute.assert_called_once()
            mock_session.commit.assert_called_once()
    
    def test_set_tenant_retention_invalid_too_low(self):
        """Test setting retention below minimum."""
        with pytest.raises(ValueError, match="Retention years must be between 1 and 30"):
            set_tenant_retention_years("test-tenant-id", 0)
    
    def test_set_tenant_retention_invalid_too_high(self):
        """Test setting retention above maximum."""
        with pytest.raises(ValueError, match="Retention years must be between 1 and 30"):
            set_tenant_retention_years("test-tenant-id", 31)
    
    def test_get_tenant_retention_error_handling(self, mock_connection_manager, mock_session):
        """Test error handling when database query fails."""
        mock_session.execute.side_effect = Exception("Database error")
        
        with patch(
            'src.services.audit_retention.get_connection_manager',
            return_value=mock_connection_manager
        ), patch(
            'src.services.audit_retention.get_audit_config'
        ) as mock_config:
            mock_config.return_value.audit_retention_years = 7
            
            retention = get_tenant_retention_years("test-tenant-id")
            
            # Should return default on error
            assert retention == 7
