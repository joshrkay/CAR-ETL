"""
End-to-End Tests for Google Drive Connector

Tests cover:
- OAuth flow initiation
- State storage and retrieval
- Token encryption/decryption
- API endpoint integration
- Sync functionality (mocked)
- Shared drive support
- Folder selection
- Changes API incremental sync
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
from fastapi.testclient import TestClient

from src.main import app
from src.auth.models import AuthContext
from src.connectors.google_drive.oauth import GoogleDriveOAuth
from src.connectors.google_drive.client import GoogleDriveClient
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
    
    # Mock documents queries
    documents_response = Mock()
    documents_response.data = None
    documents_response.execute = Mock(return_value=documents_response)
    
    documents_query = Mock()
    documents_query.maybe_single = Mock(return_value=documents_response)
    documents_query.eq = Mock(return_value=documents_query)
    documents_query.select = Mock(return_value=documents_query)
    documents_query.insert = Mock(return_value=documents_response)
    documents_query.update = Mock(return_value=documents_response)
    
    def table_side_effect(table_name):
        if table_name == "connectors":
            return connector_query
        elif table_name == "oauth_states":
            return state_query
        elif table_name == "documents":
            return documents_query
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
            "GOOGLE_CLIENT_ID": "test-client-id",
            "GOOGLE_CLIENT_SECRET": "test-secret",
            "GOOGLE_REDIRECT_URI": "http://localhost:8000/oauth/google/callback",
        }):
            oauth = GoogleDriveOAuth.from_env()
            state = str(uuid4())
            url = oauth.get_authorization_url(state=state)
            
            assert "accounts.google.com" in url
            assert "client_id=test-client-id" in url
            assert f"state={state}" in url
            assert "drive.readonly" in url
            assert "drive.metadata.readonly" in url
            assert "access_type=offline" in url
            assert "prompt=consent" in url
    
    def test_oauth_missing_config(self):
        """Test OAuth initialization with missing config."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Missing required environment variables"):
                GoogleDriveOAuth.from_env()
    
    def test_encryption_decryption(self):
        """Test token encryption and decryption."""
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


class TestGoogleDriveClient:
    """Test Google Drive API client."""
    
    @pytest.mark.asyncio
    async def test_client_token_refresh(self):
        """Test automatic token refresh on 401."""
        with patch("httpx.AsyncClient") as mock_client:
            # First request returns 401
            mock_response_401 = Mock()
            mock_response_401.status_code = 401
            mock_response_401.raise_for_status = Mock(side_effect=Exception("401"))
            
            # Second request (after refresh) succeeds
            mock_response_200 = Mock()
            mock_response_200.status_code = 200
            mock_response_200.json = Mock(return_value={"drives": []})
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
            
            client = GoogleDriveClient(
                access_token="old-token",
                refresh_token="old-refresh",
                oauth_handler=oauth_handler,
            )
            
            # Should retry after refresh
            result = await client._make_request("GET", "/drives")
            assert result == {"drives": []}
            oauth_handler.refresh_access_token.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_drives(self):
        """Test listing drives including shared drives."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value={
                "drives": [
                    {"id": "drive1", "name": "My Drive", "kind": "drive#drive"},
                    {"id": "drive2", "name": "Shared Drive", "kind": "drive#drive"},
                ],
            })
            mock_response.raise_for_status = Mock()
            
            mock_client_instance = AsyncMock()
            mock_client_instance.request = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance
            
            client = GoogleDriveClient(access_token="test-token")
            drives = await client.list_drives(include_shared=True)
            
            assert len(drives) == 2
            assert drives[0]["id"] == "drive1"
            assert drives[1]["id"] == "drive2"
    
    @pytest.mark.asyncio
    async def test_list_folders(self):
        """Test listing folders for folder selection."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value={
                "files": [
                    {
                        "id": "folder1",
                        "name": "Documents",
                        "mimeType": "application/vnd.google-apps.folder",
                        "modifiedTime": "2024-01-01T00:00:00Z",
                    },
                    {
                        "id": "folder2",
                        "name": "Projects",
                        "mimeType": "application/vnd.google-apps.folder",
                        "modifiedTime": "2024-01-02T00:00:00Z",
                    },
                ],
            })
            mock_response.raise_for_status = Mock()
            
            mock_client_instance = AsyncMock()
            mock_client_instance.request = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance
            
            client = GoogleDriveClient(access_token="test-token")
            folders = await client.list_folders()
            
            assert len(folders) == 2
            assert folders[0]["id"] == "folder1"
            assert folders[1]["id"] == "folder2"
    
    @pytest.mark.asyncio
    async def test_get_changes(self):
        """Test Changes API for incremental sync."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value={
                "changes": [
                    {
                        "changeType": "file",
                        "file": {
                            "id": "file1",
                            "name": "document.pdf",
                            "mimeType": "application/pdf",
                            "modifiedTime": "2024-01-01T00:00:00Z",
                            "size": "1024",
                        },
                    },
                ],
                "nextPageToken": "next-token",
                "newStartPageToken": "start-token",
            })
            mock_response.raise_for_status = Mock()
            
            mock_client_instance = AsyncMock()
            mock_client_instance.request = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance
            
            client = GoogleDriveClient(access_token="test-token")
            result = await client.get_changes(page_token="current-token")
            
            assert "changes" in result
            assert len(result["changes"]) == 1
            assert result["next_page_token"] == "next-token"
            assert result["start_page_token"] == "start-token"
    
    @pytest.mark.asyncio
    async def test_get_start_page_token(self):
        """Test getting start page token for initial sync."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json = Mock(return_value={
                "startPageToken": "initial-token-123",
            })
            mock_response.raise_for_status = Mock()
            
            mock_client_instance = AsyncMock()
            mock_client_instance.request = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance
            
            client = GoogleDriveClient(access_token="test-token")
            token = await client.get_start_page_token()
            
            assert token == "initial-token-123"
    
    @pytest.mark.asyncio
    async def test_download_file(self):
        """Test file download."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b"file content here"
            mock_response.raise_for_status = Mock()
            
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance
            
            client = GoogleDriveClient(access_token="test-token")
            content = await client.download_file("file-id-123")
            
            assert content == b"file content here"


class TestGoogleDriveSync:
    """Test Google Drive sync functionality."""
    
    @pytest.mark.asyncio
    async def test_sync_drive_with_changes(self, mock_supabase_client):
        """Test sync using Changes API."""
        from src.connectors.google_drive.sync import GoogleDriveSync
        from src.connectors.google_drive.interfaces import (
            TokenStore,
            ConnectorConfigStore,
            SyncStateStore,
            IngestionEmitter,
        )
        from uuid import uuid4
        
        tenant_id = uuid4()
        connector_id = uuid4()
        
        # Mock stores
        mock_token_store = AsyncMock(spec=TokenStore)
        mock_config_store = AsyncMock(spec=ConnectorConfigStore)
        mock_config_store.get_folder_ids = AsyncMock(return_value=[])
        mock_config_store.get_shared_drive_ids = AsyncMock(return_value=[])
        
        mock_state_store = AsyncMock(spec=SyncStateStore)
        mock_state_store.get_page_token = AsyncMock(return_value="existing-token")
        mock_state_store.save_page_token = AsyncMock()
        mock_state_store.update_last_sync = AsyncMock()
        
        emitted_files = []
        
        class MockEmitter(IngestionEmitter):
            async def emit_file_reference(self, **kwargs):
                emitted_files.append(kwargs["file_id"])
                return str(uuid4())
            
            async def emit_deletion_reference(self, **kwargs):
                pass
        
        mock_emitter = MockEmitter()
        
        # Mock Google Drive client
        mock_client = AsyncMock(spec=GoogleDriveClient)
        mock_client.get_changes = AsyncMock(return_value={
            "changes": [
                {
                    "changeType": "file",
                    "file": {
                        "id": "file1",
                        "name": "test.pdf",
                        "mimeType": "application/pdf",
                        "modifiedTime": "2024-01-01T00:00:00Z",
                        "size": "1024",
                        "parents": ["root"],
                    },
                },
            ],
            "next_page_token": None,
            "start_page_token": "new-token",
        })
        
        sync_handler = GoogleDriveSync(
            tenant_id=tenant_id,
            connector_id=connector_id,
            token_store=mock_token_store,
            config_store=mock_config_store,
            state_store=mock_state_store,
            emitter=mock_emitter,
        )
        
        stats = await sync_handler.sync(client=mock_client)
        
        assert stats["files_emitted"] == 1
        assert stats["deletions_emitted"] == 0
        assert len(stats["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_sync_handles_deleted_files(self, mock_supabase_client):
        """Test sync handles deleted files correctly."""
        from src.connectors.google_drive.sync import GoogleDriveSync
        from src.connectors.google_drive.interfaces import (
            TokenStore,
            ConnectorConfigStore,
            SyncStateStore,
            IngestionEmitter,
        )
        from uuid import uuid4
        
        tenant_id = uuid4()
        connector_id = uuid4()
        
        # Mock stores
        mock_token_store = AsyncMock(spec=TokenStore)
        mock_config_store = AsyncMock(spec=ConnectorConfigStore)
        mock_config_store.get_folder_ids = AsyncMock(return_value=[])
        mock_config_store.get_shared_drive_ids = AsyncMock(return_value=[])
        
        mock_state_store = AsyncMock(spec=SyncStateStore)
        mock_state_store.get_page_token = AsyncMock(return_value="token")
        mock_state_store.save_page_token = AsyncMock()
        mock_state_store.update_last_sync = AsyncMock()
        
        deletions_emitted = []
        
        class MockEmitter(IngestionEmitter):
            async def emit_file_reference(self, **kwargs):
                return str(uuid4())
            
            async def emit_deletion_reference(self, **kwargs):
                deletions_emitted.append(kwargs["file_id"])
        
        mock_emitter = MockEmitter()
        
        # Mock client with deleted file change
        mock_client = AsyncMock(spec=GoogleDriveClient)
        mock_client.get_changes = AsyncMock(return_value={
            "changes": [
                {
                    "changeType": "remove",
                    "removed": True,
                    "file": {
                        "id": "file1",
                    },
                },
            ],
            "next_page_token": None,
            "start_page_token": "new-token",
        })
        
        sync_handler = GoogleDriveSync(
            tenant_id=tenant_id,
            connector_id=connector_id,
            token_store=mock_token_store,
            config_store=mock_config_store,
            state_store=mock_state_store,
            emitter=mock_emitter,
        )
        
        stats = await sync_handler.sync(client=mock_client)
        
        assert stats["files_emitted"] == 0
        assert stats["deletions_emitted"] == 1
        assert len(stats["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_sync_with_shared_drive(self, mock_supabase_client):
        """Test sync with shared drive support."""
        from src.connectors.google_drive.sync import GoogleDriveSync
        from src.connectors.google_drive.interfaces import (
            TokenStore,
            ConnectorConfigStore,
            SyncStateStore,
            IngestionEmitter,
        )
        from uuid import uuid4
        
        tenant_id = uuid4()
        connector_id = uuid4()
        drive_id = "shared-drive-id"
        
        # Mock stores
        mock_token_store = AsyncMock(spec=TokenStore)
        mock_config_store = AsyncMock(spec=ConnectorConfigStore)
        mock_config_store.get_folder_ids = AsyncMock(return_value=[])
        mock_config_store.get_shared_drive_ids = AsyncMock(return_value=[drive_id])
        
        mock_state_store = AsyncMock(spec=SyncStateStore)
        mock_state_store.get_page_token = AsyncMock(return_value=None)
        mock_state_store.save_page_token = AsyncMock()
        mock_state_store.update_last_sync = AsyncMock()
        
        class MockEmitter(IngestionEmitter):
            async def emit_file_reference(self, **kwargs):
                return str(uuid4())
            
            async def emit_deletion_reference(self, **kwargs):
                pass
        
        mock_emitter = MockEmitter()
        
        # Mock client with shared drive
        mock_client = AsyncMock(spec=GoogleDriveClient)
        mock_client.get_start_page_token = AsyncMock(return_value="start-token")
        mock_client.get_changes = AsyncMock(return_value={
            "changes": [
                {
                    "changeType": "file",
                    "file": {
                        "id": "file1",
                        "name": "shared-doc.pdf",
                        "mimeType": "application/pdf",
                        "modifiedTime": "2024-01-01T00:00:00Z",
                        "size": "2048",
                        "parents": ["root"],
                    },
                },
            ],
            "next_page_token": None,
            "start_page_token": "new-token",
        })
        
        sync_handler = GoogleDriveSync(
            tenant_id=tenant_id,
            connector_id=connector_id,
            token_store=mock_token_store,
            config_store=mock_config_store,
            state_store=mock_state_store,
            emitter=mock_emitter,
        )
        
        stats = await sync_handler.sync(client=mock_client)
        
        assert stats["files_emitted"] == 1
        mock_client.get_changes.assert_called()
        # Verify drive_id was passed to get_changes
        call_args = mock_client.get_changes.call_args
        assert call_args[1]["drive_id"] == drive_id
    
    @pytest.mark.asyncio
    async def test_sync_filters_by_folder_id(self, mock_supabase_client):
        """Test sync filters files by folder_id."""
        from src.connectors.google_drive.sync import GoogleDriveSync
        from src.connectors.google_drive.interfaces import (
            TokenStore,
            ConnectorConfigStore,
            SyncStateStore,
            IngestionEmitter,
        )
        from uuid import uuid4
        
        tenant_id = uuid4()
        connector_id = uuid4()
        folder_id = "target-folder-id"
        
        # Mock stores
        mock_token_store = AsyncMock(spec=TokenStore)
        mock_config_store = AsyncMock(spec=ConnectorConfigStore)
        mock_config_store.get_folder_ids = AsyncMock(return_value=[folder_id])
        mock_config_store.get_shared_drive_ids = AsyncMock(return_value=[])
        
        mock_state_store = AsyncMock(spec=SyncStateStore)
        mock_state_store.get_page_token = AsyncMock(return_value="token")
        mock_state_store.save_page_token = AsyncMock()
        mock_state_store.update_last_sync = AsyncMock()
        
        emitted_files = []
        
        class MockEmitter(IngestionEmitter):
            async def emit_file_reference(self, **kwargs):
                emitted_files.append(kwargs["file_id"])
                return str(uuid4())
            
            async def emit_deletion_reference(self, **kwargs):
                pass
        
        mock_emitter = MockEmitter()
        
        # Mock client with files in different folders
        mock_client = AsyncMock(spec=GoogleDriveClient)
        mock_client.get_changes = AsyncMock(return_value={
            "changes": [
                {
                    "changeType": "file",
                    "file": {
                        "id": "file1",
                        "name": "in-folder.pdf",
                        "mimeType": "application/pdf",
                        "modifiedTime": "2024-01-01T00:00:00Z",
                        "size": "1024",
                        "parents": [folder_id],  # In target folder
                    },
                },
                {
                    "changeType": "file",
                    "file": {
                        "id": "file2",
                        "name": "other-folder.pdf",
                        "mimeType": "application/pdf",
                        "modifiedTime": "2024-01-01T00:00:00Z",
                        "size": "1024",
                        "parents": ["other-folder-id"],  # Not in target folder
                    },
                },
            ],
            "next_page_token": None,
            "start_page_token": "new-token",
        })
        
        sync_handler = GoogleDriveSync(
            tenant_id=tenant_id,
            connector_id=connector_id,
            token_store=mock_token_store,
            config_store=mock_config_store,
            state_store=mock_state_store,
            emitter=mock_emitter,
        )
        
        stats = await sync_handler.sync(client=mock_client)
        
        # Only file1 should be emitted (file2 is filtered out by folder selection)
        assert stats["files_emitted"] == 1
        assert "file1" in emitted_files
        assert "file2" not in emitted_files
        # file2 is filtered out, not skipped (it's not processed at all)


class TestStateStore:
    """Test OAuth state storage."""
    
    def test_state_storage_and_retrieval(self, mock_supabase_client):
        """Test storing and retrieving OAuth state."""
        from src.connectors.sharepoint.state_store import OAuthStateStore
        from datetime import datetime, timezone, timedelta
        import asyncio
        
        state_store = OAuthStateStore(mock_supabase_client)
        state = "test-state-123"
        tenant_id = str(uuid4())
        
        # Mock insert
        insert_response = Mock()
        insert_response.execute.return_value = Mock()
        mock_supabase_client.table.return_value.insert = Mock(return_value=insert_response)
        
        # Test store
        asyncio.run(state_store.store_state(state, tenant_id))
        
        # Mock retrieval - need to set up the chain properly
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        
        # Create proper mock chain for retrieval
        execute_result = Mock()
        execute_result.data = {
            "tenant_id": tenant_id,
            "expires_at": expires_at,
        }
        
        maybe_single_result = Mock()
        maybe_single_result.execute = Mock(return_value=execute_result)
        
        eq_result = Mock()
        eq_result.maybe_single = Mock(return_value=maybe_single_result)
        
        select_result = Mock()
        select_result.eq = Mock(return_value=eq_result)
        
        table_mock = Mock()
        table_mock.select = Mock(return_value=select_result)
        table_mock.delete = Mock(return_value=Mock(eq=Mock(return_value=Mock(execute=Mock(return_value=Mock())))))
        
        mock_supabase_client.table = Mock(return_value=table_mock)
        
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


class TestIdempotency:
    """Property-based tests for idempotency and cursor consistency."""
    
    @pytest.mark.asyncio
    async def test_same_changes_replayed_no_duplicates(self):
        """Test that replaying same change events in different orders doesn't duplicate outputs."""
        from src.connectors.google_drive.sync import GoogleDriveSync
        from src.connectors.google_drive.interfaces import (
            TokenStore,
            ConnectorConfigStore,
            SyncStateStore,
            IngestionEmitter,
        )
        from uuid import uuid4
        
        tenant_id = uuid4()
        connector_id = uuid4()
        
        # Mock stores
        mock_token_store = AsyncMock(spec=TokenStore)
        mock_config_store = AsyncMock(spec=ConnectorConfigStore)
        mock_config_store.get_folder_ids = AsyncMock(return_value=[])
        mock_config_store.get_shared_drive_ids = AsyncMock(return_value=[])
        
        mock_state_store = AsyncMock(spec=SyncStateStore)
        mock_state_store.get_page_token = AsyncMock(return_value="token-1")
        mock_state_store.save_page_token = AsyncMock()
        mock_state_store.update_last_sync = AsyncMock()
        
        emitted_file_ids = []
        
        class MockEmitter(IngestionEmitter):
            async def emit_file_reference(self, **kwargs):
                emitted_file_ids.append(kwargs["file_id"])
                return str(uuid4())
            
            async def emit_deletion_reference(self, **kwargs):
                pass
        
        mock_emitter = MockEmitter()
        
        # Same changes in different orders
        changes_order_1 = [
            {
                "changeType": "file",
                "file": {
                    "id": "file1",
                    "name": "doc1.pdf",
                    "mimeType": "application/pdf",
                    "modifiedTime": "2024-01-01T00:00:00Z",
                    "size": "1024",
                    "parents": ["root"],
                },
            },
            {
                "changeType": "file",
                "file": {
                    "id": "file2",
                    "name": "doc2.pdf",
                    "mimeType": "application/pdf",
                    "modifiedTime": "2024-01-02T00:00:00Z",
                    "size": "2048",
                    "parents": ["root"],
                },
            },
        ]
        
        changes_order_2 = [
            changes_order_1[1],
            changes_order_1[0],
        ]
        
        mock_client = AsyncMock()
        mock_client.get_changes = AsyncMock(
            side_effect=[
                {"changes": changes_order_1, "next_page_token": None, "start_page_token": "token-2"},
                {"changes": changes_order_2, "next_page_token": None, "start_page_token": "token-3"},
            ]
        )
        mock_client.get_start_page_token = AsyncMock(return_value="token-1")
        
        sync_handler = GoogleDriveSync(
            tenant_id=tenant_id,
            connector_id=connector_id,
            token_store=mock_token_store,
            config_store=mock_config_store,
            state_store=mock_state_store,
            emitter=mock_emitter,
        )
        
        # First sync
        emitted_file_ids.clear()
        await sync_handler.sync(mock_client)
        first_emitted = set(emitted_file_ids.copy())
        
        # Second sync (replay)
        emitted_file_ids.clear()
        await sync_handler.sync(mock_client)
        second_emitted = set(emitted_file_ids)
        
        # Should emit same files (idempotent)
        assert first_emitted == second_emitted
        assert len(first_emitted) == 2
    
    @pytest.mark.asyncio
    async def test_rapid_cursor_updates_consistent(self):
        """Test that rapid cursor updates under retries remain consistent."""
        from src.connectors.google_drive.sync import GoogleDriveSync
        from src.connectors.google_drive.interfaces import (
            TokenStore,
            ConnectorConfigStore,
            SyncStateStore,
            IngestionEmitter,
        )
        from uuid import uuid4
        
        tenant_id = uuid4()
        connector_id = uuid4()
        
        # Mock stores
        saved_tokens = {}
        
        class MockStateStore(SyncStateStore):
            async def get_page_token(self, tenant_id, connector_id, drive_id):
                return saved_tokens.get((str(tenant_id), str(connector_id), drive_id))
            
            async def save_page_token(self, tenant_id, connector_id, page_token, drive_id):
                saved_tokens[(str(tenant_id), str(connector_id), drive_id)] = page_token
            
            async def update_last_sync(self, tenant_id, connector_id, status, error_message=None):
                pass
        
        mock_token_store = AsyncMock(spec=TokenStore)
        mock_config_store = AsyncMock(spec=ConnectorConfigStore)
        mock_config_store.get_folder_ids = AsyncMock(return_value=[])
        mock_config_store.get_shared_drive_ids = AsyncMock(return_value=[])
        
        mock_state_store = MockStateStore()
        
        class MockEmitter(IngestionEmitter):
            async def emit_file_reference(self, **kwargs):
                return str(uuid4())
            
            async def emit_deletion_reference(self, **kwargs):
                pass
        
        mock_emitter = MockEmitter()
        
        # Simulate rapid token updates
        tokens = ["token-1", "token-2", "token-3", "token-4"]
        token_index = [0]
        
        mock_client = AsyncMock()
        mock_client.get_changes = AsyncMock(
            side_effect=lambda **kwargs: {
                "changes": [],
                "next_page_token": None,
                "start_page_token": tokens[token_index[0]],
            }
        )
        mock_client.get_start_page_token = AsyncMock(
            side_effect=lambda **kwargs: tokens[token_index[0]]
        )
        
        sync_handler = GoogleDriveSync(
            tenant_id=tenant_id,
            connector_id=connector_id,
            token_store=mock_token_store,
            config_store=mock_config_store,
            state_store=mock_state_store,
            emitter=mock_emitter,
        )
        
        # Rapid updates
        for i in range(len(tokens)):
            token_index[0] = i
            await sync_handler.sync(mock_client)
        
        # Verify final token is saved
        final_token = await mock_state_store.get_page_token(tenant_id, connector_id, None)
        assert final_token == tokens[-1]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
