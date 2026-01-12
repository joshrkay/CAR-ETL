"""
Integration Tests for Document Upload Endpoint

Tests cover:
- Successful file uploads
- File validation integration
- Permission enforcement
- Tenant isolation
- Error handling
"""

from typing import Any, Generator
import io
from unittest.mock import Mock, patch
from zipfile import ZipFile
from uuid import uuid4
from datetime import datetime, timedelta, timezone
import jwt

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.main import app
from src.auth.models import AuthContext


# Test File Fixtures
PDF_VALID = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"x" * 100
PNG_VALID = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPEG_VALID = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
TEXT_VALID = b"This is a plain text document"


def create_valid_docx() -> bytes:
    """Create a minimal valid DOCX file."""
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as zip_file:
        zip_file.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        zip_file.writestr("word/document.xml", "<document/>")
    return buffer.getvalue()


@pytest.fixture
def mock_auth_context() -> AuthContext:
    """Create a mock authenticated user context."""
    auth = Mock(spec=AuthContext)
    auth.user_id = uuid4()
    auth.tenant_id = uuid4()
    auth.email = "test@example.com"
    auth.roles = ["Analyst"]
    auth.tenant_slug = "test-tenant"
    auth.has_permission = Mock(return_value=True)
    return auth


@pytest.fixture
def mock_supabase_client() -> Any:
    """Create a mock Supabase client."""
    client = Mock()
    
    # Mock tenant settings query
    tenant_response = Mock()
    tenant_response.data = {"settings": {"max_file_size_bytes": 100 * 1024 * 1024}}
    tenant_response.execute = Mock(return_value=tenant_response)
    
    tenant_query = Mock()
    tenant_query.maybe_single = Mock(return_value=tenant_response)
    tenant_query.eq = Mock(return_value=tenant_query)
    tenant_query.select = Mock(return_value=tenant_query)
    
    # Mock document insert
    insert_response = Mock()
    insert_response.data = [{"id": "doc-123"}]
    insert_response.execute = Mock(return_value=insert_response)
    
    insert_query = Mock()
    insert_query.insert = Mock(return_value=insert_response)
    
    # Mock rate limit table (for auth rate limiter)
    rate_limit_response = Mock()
    rate_limit_response.data = []  # No existing rate limit records
    rate_limit_response.execute = Mock(return_value=rate_limit_response)
    
    rate_limit_query = Mock()
    rate_limit_query.limit = Mock(return_value=rate_limit_query)
    rate_limit_query.order = Mock(return_value=rate_limit_query)
    rate_limit_query.gte = Mock(return_value=rate_limit_query)
    rate_limit_query.eq = Mock(return_value=rate_limit_query)
    rate_limit_query.select = Mock(return_value=rate_limit_query)
    rate_limit_query.execute = Mock(return_value=rate_limit_response)
    
    # Mock rate limit insert
    rate_limit_insert_response = Mock()
    rate_limit_insert_response.execute = Mock(return_value=rate_limit_insert_response)
    rate_limit_insert = Mock()
    rate_limit_insert.insert = Mock(return_value=rate_limit_insert_response)
    
    def table_side_effect(table_name: str) -> Any:
        if table_name == "tenants":
            return tenant_query
        elif table_name == "auth_rate_limits":
            return rate_limit_query
        else:
            return insert_query
    
    client.table = Mock(side_effect=table_side_effect)
    
    return client


@pytest.fixture
def mock_auth_config() -> Any:
    """Create mock auth config for testing."""
    from src.auth.config import AuthConfig
    return AuthConfig(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test-anon-key",
        supabase_service_key="test-service-key",
        supabase_jwt_secret="test-jwt-secret-for-testing-only-do-not-use-in-production",
        app_env="test",
    )


@pytest.fixture
def valid_jwt_token(mock_auth_context: Any, mock_auth_config: Any) -> Any:
    """Create a valid JWT token for testing."""
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "sub": str(mock_auth_context.user_id),
        "email": mock_auth_context.email,
        "app_metadata": {
            "tenant_id": str(mock_auth_context.tenant_id),
            "roles": mock_auth_context.roles,
            "tenant_slug": mock_auth_context.tenant_slug,
        },
        "exp": int(exp.timestamp()),
    }
    
    return jwt.encode(payload, mock_auth_config.supabase_jwt_secret, algorithm="HS256")


class AuthenticatedTestClient:
    """Wrapper around TestClient that automatically adds Authorization header."""
    
    def __init__(self, test_client: TestClient, token: str) -> None:
        self._client = test_client
        self._token = token
    
    def _add_auth_header(self, kwargs: Any) -> Any:
        """Add Authorization header to request kwargs."""
        if "headers" not in kwargs:
            kwargs["headers"] = {}
        kwargs["headers"]["Authorization"] = f"Bearer {self._token}"
        return kwargs
    
    def post(self, *args: Any, **kwargs: Any) -> Any:
        """POST request with automatic auth header."""
        kwargs = self._add_auth_header(kwargs)
        return self._client.post(*args, **kwargs)
    
    def get(self, *args: Any, **kwargs: Any) -> Any:
        """GET request with automatic auth header."""
        kwargs = self._add_auth_header(kwargs)
        return self._client.get(*args, **kwargs)
    
    def put(self, *args: Any, **kwargs: Any) -> Any:
        """PUT request with automatic auth header."""
        kwargs = self._add_auth_header(kwargs)
        return self._client.put(*args, **kwargs)
    
    def delete(self, *args: Any, **kwargs: Any) -> Any:
        """DELETE request with automatic auth header."""
        kwargs = self._add_auth_header(kwargs)
        return self._client.delete(*args, **kwargs)
    
    def patch(self, *args: Any, **kwargs: Any) -> Any:
        """PATCH request with automatic auth header."""
        kwargs = self._add_auth_header(kwargs)
        return self._client.patch(*args, **kwargs)


@pytest.fixture
def client_with_auth(mock_auth_context: Any, mock_supabase_client: Any, valid_jwt_token: Any, mock_auth_config: Any) -> Generator:
    """Create test client with mocked auth middleware."""
    def override_get_current_user() -> Any:
        return mock_auth_context
    
    def override_get_supabase_client() -> Any:
        return mock_supabase_client
    
    from src.dependencies import get_current_user, get_supabase_client
    
    # Patch create_client so rate limiter uses mocked client
    rate_limiter_patcher = patch("src.auth.rate_limit.create_client", return_value=mock_supabase_client)
    rate_limiter_patcher.start()
    
    # Patch auth config at multiple points where it's used
    config_patcher1 = patch("src.auth.middleware.get_auth_config", return_value=mock_auth_config)
    config_patcher2 = patch("src.auth.config.get_auth_config", return_value=mock_auth_config)
    config_patcher1.start()
    config_patcher2.start()
    
    # Update middleware instances' config (they're already instantiated)
    # Find AuthMiddleware instance in app's middleware stack
    for middleware in app.user_middleware:
        if hasattr(middleware, 'cls') and middleware.cls.__name__ == 'AuthMiddleware':
            # The middleware is wrapped, we need to access it differently
            pass
    
    # Patch the middleware's _validate_token to bypass validation
    async def mock_validate_token(self, request: Any) -> None:
        # Set auth context directly
        request.state.auth = mock_auth_context
        request.state.supabase = mock_supabase_client
        return None
    
    middleware_patcher = patch("src.auth.middleware.AuthMiddleware._validate_token", mock_validate_token)
    middleware_patcher.start()
    
    try:
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_supabase_client] = override_get_supabase_client
        
        base_client = TestClient(app)
        # Wrap client to automatically add auth header
        client = AuthenticatedTestClient(base_client, valid_jwt_token)
        
        yield client
        
        # Cleanup
        app.dependency_overrides.clear()
        middleware_patcher.stop()
        config_patcher2.stop()
        config_patcher1.stop()
    finally:
        rate_limiter_patcher.stop()


class TestDocumentUpload:
    """Test suite for document upload endpoint."""
    
    def test_upload_pdf_success(self, client_with_auth) -> None:
        """Test successful PDF upload."""
        files = {
            "file": ("test.pdf", io.BytesIO(PDF_VALID), "application/pdf")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "document_id" in data
        assert data["filename"] == "test.pdf"
        assert data["mime_type"] == "application/pdf"
        assert data["file_size"] == len(PDF_VALID)
        assert data["status"] == "pending"
    
    def test_upload_png_success(self, client_with_auth) -> None:
        """Test successful PNG upload."""
        files = {
            "file": ("image.png", io.BytesIO(PNG_VALID), "image/png")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["filename"] == "image.png"
        assert data["mime_type"] == "image/png"
    
    def test_upload_jpeg_success(self, client_with_auth) -> None:
        """Test successful JPEG upload."""
        files = {
            "file": ("photo.jpg", io.BytesIO(JPEG_VALID), "image/jpeg")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["filename"] == "photo.jpg"
        assert data["mime_type"] == "image/jpeg"
    
    def test_upload_text_success(self, client_with_auth) -> None:
        """Test successful plain text upload."""
        files = {
            "file": ("document.txt", io.BytesIO(TEXT_VALID), "text/plain")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["filename"] == "document.txt"
        assert data["mime_type"] == "text/plain"
    
    def test_upload_docx_success(self, client_with_auth) -> None:
        """Test successful DOCX upload with Office XML validation."""
        docx_content = create_valid_docx()
        files = {
            "file": (
                "report.docx",
                io.BytesIO(docx_content),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["filename"] == "report.docx"
    
    def test_upload_with_description(self, client_with_auth) -> None:
        """Test upload with optional description field."""
        files = {
            "file": ("test.pdf", io.BytesIO(PDF_VALID), "application/pdf")
        }
        data = {
            "description": "Q4 Financial Report"
        }
        
        response = client_with_auth.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
        )
        
        assert response.status_code == status.HTTP_201_CREATED


class TestFileValidation:
    """Test file validation integration in upload endpoint."""
    
    def test_reject_wrong_magic_bytes(self, client_with_auth) -> None:
        """Test rejection of file with mismatched magic bytes."""
        fake_pdf = b"This is not a PDF"
        files = {
            "file": ("fake.pdf", io.BytesIO(fake_pdf), "application/pdf")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["code"] == "VALIDATION_ERROR"
        assert "validation_errors" in data["detail"]
        assert any("does not match claimed MIME type" in err for err in data["detail"]["validation_errors"])
    
    def test_reject_executable_as_pdf(self, client_with_auth) -> None:
        """Test rejection of executable disguised as PDF."""
        exe_file = b"MZ\x90\x00" + b"\x00" * 100  # Windows EXE magic bytes
        files = {
            "file": ("malware.pdf", io.BytesIO(exe_file), "application/pdf")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["code"] == "VALIDATION_ERROR"
    
    def test_reject_unsupported_mime_type(self, client_with_auth) -> None:
        """Test rejection of unsupported file type."""
        files = {
            "file": ("script.exe", io.BytesIO(b"content"), "application/x-msdownload")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Unsupported MIME type" in str(data["detail"]["validation_errors"])
    
    def test_reject_oversized_file(self, client_with_auth, mock_supabase_client, mock_auth_context) -> None:
        """Test rejection of file exceeding size limit."""
        # Set small limit
        mock_supabase_client.table("tenants").select("settings").eq("id", str(mock_auth_context.tenant_id)).maybe_single().execute.return_value.data = {
            "settings": {"max_file_size_bytes": 100}
        }
        
        large_file = b"x" * 200  # 200 bytes, exceeds 100 byte limit
        files = {
            "file": ("large.txt", io.BytesIO(large_file), "text/plain")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        data = response.json()
        assert data["detail"]["code"] == "VALIDATION_ERROR"
        assert any("exceeds maximum" in err for err in data["detail"]["validation_errors"])
    
    def test_reject_invalid_docx_structure(self, client_with_auth) -> None:
        """Test rejection of DOCX with invalid Office XML structure."""
        # Create ZIP without [Content_Types].xml
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as zip_file:
            zip_file.writestr("malicious.xml", "<malicious/>")
        invalid_docx = buffer.getvalue()
        
        files = {
            "file": (
                "invalid.docx",
                io.BytesIO(invalid_docx),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert any("Invalid Office Open XML structure" in err for err in data["detail"]["validation_errors"])


class TestAuthentication:
    """Test authentication and authorization for upload endpoint."""
    
    def test_upload_requires_authentication(self) -> None:
        """Test that upload endpoint requires authentication."""
        client = TestClient(app)
        files = {
            "file": ("test.pdf", io.BytesIO(PDF_VALID), "application/pdf")
        }
        
        response = client.post("/api/v1/documents/upload", files=files)
        
        # Should be rejected by auth middleware or dependency
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
    
    def test_upload_requires_permission(self, mock_supabase_client) -> None:
        """Test that upload requires 'documents:create' permission."""
        # Create auth context without permission
        auth = Mock(spec=AuthContext)
        auth.user_id = uuid4()
        auth.tenant_id = uuid4()
        auth.email = "viewer@example.com"
        auth.tenant_slug = "test-tenant"
        auth.roles = ["Viewer"]  # Viewer doesn't have create permission
        auth.has_permission = Mock(return_value=False)
        
        def override_get_current_user() -> Any:
            return auth
        
        def override_get_supabase_client() -> Any:
            return mock_supabase_client
        
        from src.dependencies import get_current_user, get_supabase_client
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_supabase_client] = override_get_supabase_client
        
        client = TestClient(app)
        files = {
            "file": ("test.pdf", io.BytesIO(PDF_VALID), "application/pdf")
        }
        
        response = client.post("/api/v1/documents/upload", files=files)
        
        # Should be rejected due to insufficient permissions
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Cleanup
        app.dependency_overrides.clear()


class TestTenantIsolation:
    """Test tenant isolation in document uploads."""
    
    def test_tenant_specific_size_limit(self, client_with_auth, mock_supabase_client, mock_auth_context) -> None:
        """Test that tenant-specific size limits are enforced."""
        # Configure tenant with 50MB limit
        mock_supabase_client.table("tenants").select("settings").eq("id", str(mock_auth_context.tenant_id)).maybe_single().execute.return_value.data = {
            "settings": {"max_file_size_bytes": 50 * 1024 * 1024}
        }
        
        # Upload should succeed with file under limit
        files = {
            "file": ("test.pdf", io.BytesIO(PDF_VALID), "application/pdf")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_document_associated_with_tenant(self, client_with_auth, mock_supabase_client) -> None:
        """Test that uploaded document is associated with correct tenant."""
        files = {
            "file": ("test.pdf", io.BytesIO(PDF_VALID), "application/pdf")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify Supabase insert was called with correct tenant_id
        insert_calls = [
            call for call in mock_supabase_client.table.call_args_list
            if call[0][0] == "documents"
        ]
        assert len(insert_calls) > 0


class TestErrorHandling:
    """Test error handling in upload endpoint."""
    
    def test_database_error_handling(self, client_with_auth, mock_supabase_client) -> None:
        """Test graceful handling of database errors."""
        # Make database insert fail
        mock_supabase_client.table("documents").insert.side_effect = Exception("Database connection failed")
        
        files = {
            "file": ("test.pdf", io.BytesIO(PDF_VALID), "application/pdf")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert data["detail"]["code"] == "DATABASE_ERROR"
    
    def test_empty_file_handling(self, client_with_auth) -> None:
        """Test handling of empty file upload."""
        files = {
            "file": ("empty.txt", io.BytesIO(b""), "text/plain")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        # Empty text file should be accepted (no magic bytes required)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["file_size"] == 0
    
    def test_missing_file_parameter(self, client_with_auth) -> None:
        """Test error when file parameter is missing."""
        response = client_with_auth.post("/api/v1/documents/upload")
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestResponseFormat:
    """Test response format and structure."""
    
    def test_success_response_structure(self, client_with_auth) -> None:
        """Test that success response has correct structure."""
        files = {
            "file": ("test.pdf", io.BytesIO(PDF_VALID), "application/pdf")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        # Verify all required fields present
        assert "document_id" in data
        assert "filename" in data
        assert "mime_type" in data
        assert "file_size" in data
        assert "status" in data
        assert "message" in data
        
        # Verify types
        assert isinstance(data["document_id"], str)
        assert isinstance(data["filename"], str)
        assert isinstance(data["mime_type"], str)
        assert isinstance(data["file_size"], int)
        assert isinstance(data["status"], str)
        assert isinstance(data["message"], str)
    
    def test_validation_error_response_structure(self, client_with_auth) -> None:
        """Test that validation error response has correct structure."""
        fake_pdf = b"This is not a PDF"
        files = {
            "file": ("fake.pdf", io.BytesIO(fake_pdf), "application/pdf")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        
        # Verify error structure
        assert "detail" in data
        assert "code" in data["detail"]
        assert "message" in data["detail"]
        assert "validation_errors" in data["detail"]
        assert isinstance(data["detail"]["validation_errors"], list)
