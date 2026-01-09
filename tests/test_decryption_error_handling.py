"""
Tests for improved error handling in token decryption and OAuth state management.

Tests cover:
- Decryption with missing encryption keys
- Decryption with invalid/corrupted tokens
- State retrieval with database exceptions
- State retrieval with missing/expired states
"""
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4
from datetime import datetime, timezone, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

import pytest
from fastapi import HTTPException, status

from src.api.routes.connectors import _decrypt_connector_config
from src.connectors.sharepoint.state_store import OAuthStateStore
from src.utils.encryption import encrypt_value, decrypt_value


class TestDecryptionErrorHandling:
    """Test improved decryption error handling."""
    
    def test_decrypt_with_missing_encryption_keys(self):
        """Test decryption fails gracefully when encryption keys are not configured."""
        config = {
            "access_token": "some-encrypted-token",
            "refresh_token": "some-encrypted-refresh-token",
        }
        
        # Clear all encryption-related env vars
        with patch.dict(os.environ, {}, clear=False):
            # Remove encryption keys temporarily
            env_backup = {}
            for key in ["ENCRYPTION_KEY", "SUPABASE_JWT_SECRET"]:
                if key in os.environ:
                    env_backup[key] = os.environ.pop(key)
            
            try:
                with pytest.raises(HTTPException) as exc_info:
                    _decrypt_connector_config(config)
                
                assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                assert exc_info.value.detail["code"] == "DECRYPTION_CONFIG_ERROR"
                assert "Encryption keys not configured" in exc_info.value.detail["message"]
            finally:
                # Restore env vars
                os.environ.update(env_backup)
    
    def test_decrypt_with_corrupted_access_token(self):
        """Test decryption fails gracefully with corrupted access token."""
        import base64
        from cryptography.fernet import Fernet
        
        # Set up encryption key for test
        test_key = Fernet.generate_key()
        
        with patch.dict(os.environ, {
            "ENCRYPTION_KEY": base64.urlsafe_b64encode(test_key).decode(),
        }):
            config = {
                "access_token": "corrupted-invalid-base64!@#$%",
                "site_id": "test-site",
            }
            
            with pytest.raises(HTTPException) as exc_info:
                _decrypt_connector_config(config)
            
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert exc_info.value.detail["code"] == "DECRYPTION_ERROR"
            assert "access token" in exc_info.value.detail["message"].lower()
    
    def test_decrypt_with_corrupted_refresh_token(self):
        """Test decryption fails gracefully with corrupted refresh token."""
        import base64
        from cryptography.fernet import Fernet
        
        # Set up encryption key for test
        test_key = Fernet.generate_key()
        
        with patch.dict(os.environ, {
            "ENCRYPTION_KEY": base64.urlsafe_b64encode(test_key).decode(),
        }):
            # Create a valid encrypted access token
            valid_token = encrypt_value("valid-access-token")
            
            config = {
                "access_token": valid_token,
                "refresh_token": "corrupted-invalid-base64!@#$%",
            }
            
            with pytest.raises(HTTPException) as exc_info:
                _decrypt_connector_config(config)
            
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert exc_info.value.detail["code"] == "DECRYPTION_ERROR"
            assert "refresh token" in exc_info.value.detail["message"].lower()
    
    def test_decrypt_with_wrong_encryption_key(self):
        """Test decryption fails when token was encrypted with different key."""
        import base64
        from cryptography.fernet import Fernet
        
        # Encrypt with one key
        key1 = Fernet.generate_key()
        with patch.dict(os.environ, {
            "ENCRYPTION_KEY": base64.urlsafe_b64encode(key1).decode(),
        }):
            encrypted_token = encrypt_value("my-secret-token")
        
        # Try to decrypt with different key
        key2 = Fernet.generate_key()
        with patch.dict(os.environ, {
            "ENCRYPTION_KEY": base64.urlsafe_b64encode(key2).decode(),
        }):
            config = {
                "access_token": encrypted_token,
            }
            
            with pytest.raises(HTTPException) as exc_info:
                _decrypt_connector_config(config)
            
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert exc_info.value.detail["code"] == "DECRYPTION_ERROR"
            assert "encryption key mismatch" in exc_info.value.detail["message"].lower()
    
    def test_decrypt_success_with_valid_tokens(self):
        """Test successful decryption with valid tokens."""
        import base64
        from cryptography.fernet import Fernet
        
        # Set up encryption key for test
        test_key = Fernet.generate_key()
        
        with patch.dict(os.environ, {
            "ENCRYPTION_KEY": base64.urlsafe_b64encode(test_key).decode(),
        }):
            original_access = "test-access-token-123"
            original_refresh = "test-refresh-token-456"
            
            config = {
                "access_token": encrypt_value(original_access),
                "refresh_token": encrypt_value(original_refresh),
                "site_id": "test-site",
            }
            
            decrypted = _decrypt_connector_config(config)
            
            assert decrypted["access_token"] == original_access
            assert decrypted["refresh_token"] == original_refresh
            assert decrypted["site_id"] == "test-site"
    
    def test_decrypt_with_empty_tokens(self):
        """Test decryption handles empty token values."""
        import base64
        from cryptography.fernet import Fernet
        
        # Set up encryption key for test
        test_key = Fernet.generate_key()
        
        with patch.dict(os.environ, {
            "ENCRYPTION_KEY": base64.urlsafe_b64encode(test_key).decode(),
        }):
            config = {
                "access_token": "",
                "refresh_token": "",
            }
            
            decrypted = _decrypt_connector_config(config)
            
            assert decrypted["access_token"] == ""
            assert decrypted["refresh_token"] == ""


class TestStateStoreErrorHandling:
    """Test improved OAuth state store error handling."""
    
    @pytest.mark.asyncio
    async def test_store_state_with_empty_state(self):
        """Test storing empty state raises appropriate error."""
        mock_supabase = Mock()
        state_store = OAuthStateStore(mock_supabase)
        
        with pytest.raises(ValueError, match="State parameter cannot be empty"):
            await state_store.store_state(state="", tenant_id="test-tenant")
    
    @pytest.mark.asyncio
    async def test_store_state_with_empty_tenant_id(self):
        """Test storing with empty tenant_id raises appropriate error."""
        mock_supabase = Mock()
        state_store = OAuthStateStore(mock_supabase)
        
        with pytest.raises(ValueError, match="Tenant ID cannot be empty"):
            await state_store.store_state(state="test-state", tenant_id="")
    
    @pytest.mark.asyncio
    async def test_store_state_database_error(self):
        """Test store_state handles database errors gracefully."""
        mock_supabase = Mock()
        mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception("Database connection failed")
        
        state_store = OAuthStateStore(mock_supabase)
        
        with pytest.raises(Exception, match="Database connection failed"):
            await state_store.store_state(state="test-state", tenant_id="test-tenant")
    
    @pytest.mark.asyncio
    async def test_get_tenant_id_with_empty_state(self):
        """Test get_tenant_id with empty state returns None."""
        mock_supabase = Mock()
        state_store = OAuthStateStore(mock_supabase)
        
        result = await state_store.get_tenant_id("")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_tenant_id_state_not_found(self):
        """Test get_tenant_id when state doesn't exist."""
        mock_supabase = Mock()
        
        # Mock response with no data
        mock_response = Mock()
        mock_response.data = None
        
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_response
        
        state_store = OAuthStateStore(mock_supabase)
        result = await state_store.get_tenant_id("non-existent-state")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_tenant_id_expired_state(self):
        """Test get_tenant_id with expired state."""
        mock_supabase = Mock()
        
        # Mock response with expired state
        expired_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        mock_response = Mock()
        mock_response.data = {
            "tenant_id": "test-tenant-id",
            "expires_at": expired_time,
        }
        
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_response
        
        # Mock delete for cleanup
        mock_delete = Mock()
        mock_delete.execute.return_value = Mock()
        mock_supabase.table.return_value.delete.return_value.eq.return_value = mock_delete
        
        state_store = OAuthStateStore(mock_supabase)
        result = await state_store.get_tenant_id("expired-state")
        
        assert result is None
        # Verify cleanup was attempted
        mock_supabase.table.return_value.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_tenant_id_invalid_expires_at(self):
        """Test get_tenant_id with invalid expires_at format."""
        mock_supabase = Mock()
        
        # Mock response with invalid expires_at
        mock_response = Mock()
        mock_response.data = {
            "tenant_id": "test-tenant-id",
            "expires_at": "invalid-date-format",
        }
        
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_response
        
        state_store = OAuthStateStore(mock_supabase)
        result = await state_store.get_tenant_id("test-state")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_tenant_id_missing_tenant_id(self):
        """Test get_tenant_id when tenant_id is missing from response."""
        mock_supabase = Mock()
        
        # Mock response without tenant_id
        future_time = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        mock_response = Mock()
        mock_response.data = {
            "expires_at": future_time,
            # tenant_id is missing
        }
        
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_response
        
        state_store = OAuthStateStore(mock_supabase)
        result = await state_store.get_tenant_id("test-state")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_tenant_id_database_error(self):
        """Test get_tenant_id handles database errors gracefully."""
        mock_supabase = Mock()
        
        # Simulate database error
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.side_effect = Exception("Database error")
        
        state_store = OAuthStateStore(mock_supabase)
        result = await state_store.get_tenant_id("test-state")
        
        # Should return None instead of raising
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_tenant_id_success(self):
        """Test successful state retrieval."""
        mock_supabase = Mock()
        
        # Mock valid state response
        future_time = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        mock_response = Mock()
        mock_response.data = {
            "tenant_id": "test-tenant-123",
            "expires_at": future_time,
        }
        
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_response
        
        # Mock delete for cleanup
        mock_delete = Mock()
        mock_delete.execute.return_value = Mock()
        mock_supabase.table.return_value.delete.return_value.eq.return_value = mock_delete
        
        state_store = OAuthStateStore(mock_supabase)
        result = await state_store.get_tenant_id("test-state")
        
        assert result == "test-tenant-123"
        # Verify cleanup was attempted
        mock_supabase.table.return_value.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_tenant_id_cleanup_failure(self):
        """Test get_tenant_id handles cleanup failures gracefully."""
        mock_supabase = Mock()
        
        # Mock valid state response
        future_time = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        mock_response = Mock()
        mock_response.data = {
            "tenant_id": "test-tenant-123",
            "expires_at": future_time,
        }
        
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_response
        
        # Mock delete that fails
        mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.side_effect = Exception("Delete failed")
        
        state_store = OAuthStateStore(mock_supabase)
        result = await state_store.get_tenant_id("test-state")
        
        # Should still return tenant_id even if cleanup fails
        assert result == "test-tenant-123"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
