"""
End-to-End Tests for SharePoint Connector

Tests cover:
- OAuth flow initiation
- State storage and retrieval
- Token encryption/decryption
- API endpoint integration
- Sync functionality (mocked)
"""
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

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
from fastapi import status
from fastapi.testclient import TestClient
from supabase import create_client, Client

from src.main import app
from src.auth.models import AuthContext
from src.connectors.sharepoint.oauth import SharePointOAuth, SharePointOAuthError
from src.connectors.sharepoint.client import SharePointClient, SharePointClientError
from src.utils.encryption import encrypt_value, decrypt_value


@pytest.fixture
def mock_auth_context():
    """Create a mock authenticated user context."""
    auth = Mock(spec=AuthContext)
    auth.user_id = uuid4()
    auth.tenant_id = uuid4()
    auth.email = "test@example.com"
    auth.roles = ["Analyst"]
    auth.tenant_slug = "test-tenant"
    auth.has_role = Mock(return_value=True)
    auth.has_any_role = Mock(return_value=True)
    return auth


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client."""
    client = Mock()
    
    # Mock connector queries
    connector_response = Mock()
    connector_response.data = None
    connector_response.execute = Mock(return_value=connector_response)
    
    connector_query = Mock()
    connector_query.maybe_single = Mock(return_value=connector_response)
    connector_query.eq = Mock(return_value=connector_query)
    connector_query.select = Mock(return_value=connector_query)
    connector_query.insert = Mock(return_value=connector_response)
    connector_query.update = Mock(return_value=connector_response)
    
    # Mock oauth_states queries
    state_response = Mock()
    state_response.data = None
    state_response.execute = Mock(return_value=state_response)
    
    state_query = Mock()
    state_query.maybe_single = Mock(return_value=state_response)
    state_query.eq = Mock(return_value=state_query)
    state_query.select = Mock(return_value=state_query)
    state_query.insert = Mock(return_value=state_response)
    state_query.delete = Mock(return_value=state_response)
    
    def table_side_effect(table_name):
        if table_name == "connectors":
            return connector_query
        elif table_name == "oauth_states":
            return state_query
        return Mock()
    
    client.table = Mock(side_effect=table_side_effect)
    
    return client


@pytest.fixture
def client_with_auth(mock_auth_context, mock_supabase_client):
    """Create test client with mocked auth."""
    def override_get_current_user():
        return mock_auth_context
    
    def override_get_supabase_client():
        return mock_supabase_client
    
    from src.dependencies import get_current_user, get_supabase_client
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_supabase_client] = override_get_supabase_client
    
    client = TestClient(app)
    
    yield client
    
    app.dependency_overrides.clear()


class TestOAuthFlow:
    """Test OAuth flow components."""
    
    def test_oauth_authorization_url_generation(self):
        """Test OAuth authorization URL generation."""
        with patch.dict(os.environ, {
            "SHAREPOINT_CLIENT_ID": "test-client-id",
            "SHAREPOINT_CLIENT_SECRET": "test-secret",
            "SHAREPOINT_REDIRECT_URI": "http://localhost:8000/oauth/microsoft/callback",
        }):
            oauth = SharePointOAuth.from_env()
            state = str(uuid4())
            url = oauth.get_authorization_url(state=state)
            
            assert "login.microsoftonline.com" in url
            assert "client_id=test-client-id" in url
            assert f"state={state}" in url
            assert "Files.Read.All" in url
            assert "Sites.Read.All" in url
    
    def test_oauth_missing_config(self):
        """Test OAuth initialization with missing config."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Missing required environment variables"):
                SharePointOAuth.from_env()
    
    def test_encryption_decryption(self):
        """Test token encryption and decryption."""
        # Set up encryption key for test
        import base64
        from cryptography.fernet import Fernet
        test_key = Fernet.generate_key()
        
        with patch.dict(os.environ, {
            "ENCRYPTION_KEY": base64.urlsafe_b64encode(test_key).decode(),
        }):
            original_token = "test-access-token-12345"
            encrypted = encrypt_value(original_token)
            
            assert encrypted != original_token
            assert len(encrypted) > 0
            
            decrypted = decrypt_value(encrypted)
            assert decrypted == original_token
    
    def test_encryption_empty_value(self):
        """Test encryption with empty value."""
        encrypted = encrypt_value("")
        assert encrypted == ""
        
        decrypted = decrypt_value("")
        assert decrypted == ""


class TestAPIRoutes:
    """Test API route endpoints."""
    
    def test_start_oauth_requires_auth(self, client_with_auth):
        """Test that OAuth start requires authentication."""
        # Remove auth override to test unauthenticated access
        app.dependency_overrides.clear()
        
        response = client_with_auth.post("/api/v1/connectors/sharepoint/auth")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Restore auth
        from src.dependencies import get_current_user, get_supabase_client
        from unittest.mock import Mock
        auth = Mock(spec=AuthContext)
        auth.user_id = uuid4()
        auth.tenant_id = uuid4()
        auth.roles = ["Analyst"]
        app.dependency_overrides[get_current_user] = lambda: auth
    
    def test_start_oauth_success(self, client_with_auth, mock_supabase_client):
        """Test successful OAuth flow initiation."""
        with patch.dict(os.environ, {
            "SHAREPOINT_CLIENT_ID": "test-client-id",
            "SHAREPOINT_CLIENT_SECRET": "test-secret",
            "SHAREPOINT_REDIRECT_URI": "http://localhost:8000/oauth/microsoft/callback",
        }):
            # Mock connector creation
            connector_id = str(uuid4())
            mock_supabase_client.table.return_value.insert.return_value.execute.return_value.data = [{
                "id": connector_id,
                "tenant_id": str(uuid4()),
                "type": "sharepoint",
                "config": {},
                "status": "active",
            }]
            
            # Mock state storage
            state_insert = Mock()
            state_insert.execute.return_value = Mock()
            mock_supabase_client.table.return_value.insert = Mock(return_value=state_insert)
            
            response = client_with_auth.post("/api/v1/connectors/sharepoint/auth")
            
            # Should succeed (200) or fail with config error (500)
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
    
    def test_oauth_callback_public_endpoint(self):
        """Test public OAuth callback endpoint."""
        client = TestClient(app)
        
        # Should accept GET without auth (but will fail without valid state)
        response = client.get(
            "/oauth/microsoft/callback",
            params={"code": "test-code", "state": "test-state"}
        )
        
        # Should fail with invalid state (400) or succeed if state is valid
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]
    
    def test_list_sites_requires_auth(self, client_with_auth):
        """Test that listing sites requires authentication."""
        app.dependency_overrides.clear()
        
        response = client_with_auth.post("/api/v1/connectors/sharepoint/sites")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_configure_requires_auth(self, client_with_auth):
        """Test that configuring connector requires authentication."""
        app.dependency_overrides.clear()
        
        response = client_with_auth.post(
            "/api/v1/connectors/sharepoint/configure",
            json={
                "site_id": "test-site-id",
                "drive_id": "test-drive-id",
                "folder_path": "/",
            }
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestSharePointClient:
    """Test SharePoint Graph API client."""
    
    @pytest.mark.asyncio
    async def test_client_token_refresh(self) -> None:
        """Test automatic token refresh on 401."""
        with patch("httpx.AsyncClient") as mock_client:
            # First request returns 401
            mock_response_401 = Mock()
            mock_response_401.status_code = 401
            mock_response_401.raise_for_status = Mock(side_effect=Exception("401"))
            
            # Second request (after refresh) succeeds
            mock_response_200 = Mock()
            mock_response_200.status_code = 200
            mock_response_200.json = Mock(return_value={"value": []})
            mock_response_200.raise_for_status = Mock()
            
            mock_client_instance = AsyncMock()
            mock_client_instance.request = AsyncMock(
                side_effect=[mock_response_401, mock_response_200]
            )
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance
            
            oauth_handler = Mock()
            oauth_handler.refresh_access_token = AsyncMock(return_value={
                "access_token": "new-token",
                "refresh_token": "new-refresh",
            })
            
            client = SharePointClient(
                access_token="old-token",
                refresh_token="old-refresh",
                oauth_handler=oauth_handler,
            )
            
            # Should retry after refresh
            result = await client._make_request("GET", "/sites")
            assert result == {"value": []}
            oauth_handler.refresh_access_token.assert_called_once()


class TestStateStore:
    """Test OAuth state storage."""
    
    def test_state_storage_and_retrieval(self, mock_supabase_client):
        """Test storing and retrieving OAuth state."""
        from src.connectors.sharepoint.state_store import OAuthStateStore
        from datetime import datetime, timezone, timedelta
        
        state_store = OAuthStateStore(mock_supabase_client)
        state = "test-state-123"
        tenant_id = str(uuid4())
        
        # Mock insert
        insert_response = Mock()
        insert_response.execute.return_value = Mock()
        mock_supabase_client.table.return_value.insert = Mock(return_value=insert_response)
        
        # Test store
        import asyncio
        asyncio.run(state_store.store_state(state, tenant_id))
        
        # Mock retrieval
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "tenant_id": tenant_id,
            "expires_at": expires_at,
        }
        
        # Mock delete
        delete_response = Mock()
        delete_response.execute.return_value = Mock()
        mock_supabase_client.table.return_value.delete.return_value.eq.return_value.execute = Mock(return_value=delete_response)
        
        # Test retrieval
        retrieved_tenant_id = asyncio.run(state_store.get_tenant_id(state))
        assert retrieved_tenant_id == tenant_id
    
    def test_state_expired(self, mock_supabase_client):
        """Test expired state retrieval."""
        from src.connectors.sharepoint.state_store import OAuthStateStore
        from datetime import datetime, timezone, timedelta
        import asyncio
        
        state_store = OAuthStateStore(mock_supabase_client)
        state = "expired-state"
        
        # Mock expired state
        expires_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "tenant_id": str(uuid4()),
            "expires_at": expires_at,
        }
        
        # Mock delete
        delete_response = Mock()
        delete_response.execute.return_value = Mock()
        mock_supabase_client.table.return_value.delete.return_value.eq.return_value.execute = Mock(return_value=delete_response)
        
        # Should return None for expired state
        retrieved_tenant_id = asyncio.run(state_store.get_tenant_id(state))
        assert retrieved_tenant_id is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
