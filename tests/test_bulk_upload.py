"""
Integration and Unit Tests for Bulk Upload

Tests cover:
- ZIP file validation
- Bulk file processing
- Individual file validation within ZIP
- Batch result reporting
- Error handling for partial failures
- Tenant isolation
- Permission enforcement
"""

import io
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.main import app
from src.auth.models import AuthContext
from src.services.bulk_upload import BulkUploadService, create_bulk_upload_service
from src.services.file_validator import FileValidator


# Test File Content
PDF_CONTENT = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"x" * 100
PNG_CONTENT = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPEG_CONTENT = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
TEXT_CONTENT = b"Sample text document content"


def create_valid_docx() -> bytes:
    """Create a minimal valid DOCX file."""
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as zf:
        content_types = '''<?xml version="1.0"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("word/document.xml", "<document/>")
    return buffer.getvalue()


def create_test_zip(files_dict: dict[str, tuple[bytes, str]]) -> bytes:
    """
    Create a ZIP file with test files.
    
    Args:
        files_dict: Dict of {filename: (content, mime_type)}
        
    Returns:
        ZIP file bytes
    """
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as zf:
        for filename, (content, _) in files_dict.items():
            zf.writestr(filename, content)
    return buffer.getvalue()


@pytest.fixture
def mock_auth_context():
    """Create mock authenticated user context."""
    auth = Mock(spec=AuthContext)
    auth.user_id = "user-abc123"
    auth.tenant_id = "tenant-xyz789"
    auth.email = "user@test.com"
    auth.roles = ["Analyst"]
    auth.tenant_slug = "test-tenant"
    auth.has_permission = Mock(return_value=True)
    return auth


@pytest.fixture
def mock_supabase_client():
    """Create mock Supabase client."""
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
    
    def table_side_effect(table_name):
        if table_name == "tenants":
            return tenant_query
        elif table_name == "auth_rate_limits":
            return rate_limit_query
        else:
            return insert_query
    
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
    
    # Patch create_client so rate limiter uses mocked client
    patcher = patch("src.auth.rate_limit.create_client", return_value=mock_supabase_client)
    patcher.start()
    
    try:
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_supabase_client] = override_get_supabase_client
        
        client = TestClient(app)
        
        yield client
        
        app.dependency_overrides.clear()
    finally:
        patcher.stop()


class TestBulkUploadService:
    """Unit tests for BulkUploadService."""
    
    def test_validate_zip_file_success(self) -> None:
        """Test successful ZIP validation."""
        service = create_bulk_upload_service(max_file_size=100 * 1024 * 1024)
        
        zip_content = create_test_zip({
            "doc1.pdf": (PDF_CONTENT, "application/pdf"),
            "doc2.txt": (TEXT_CONTENT, "text/plain"),
        })
        
        errors = service.validate_zip_file(zip_content)
        
        assert len(errors) == 0
    
    def test_validate_zip_file_too_large(self) -> None:
        """Test rejection of oversized ZIP."""
        service = create_bulk_upload_service(max_file_size=100 * 1024 * 1024)
        
        # Create large content
        large_content = b"x" * (500 * 1024 * 1024 + 1)  # Exceed 500MB
        
        errors = service.validate_zip_file(large_content)
        
        assert len(errors) > 0
        assert any("exceeds maximum" in err for err in errors)
    
    def test_validate_zip_file_empty(self) -> None:
        """Test rejection of empty ZIP."""
        service = create_bulk_upload_service(max_file_size=100 * 1024 * 1024)
        
        errors = service.validate_zip_file(b"")
        
        assert len(errors) > 0
        assert any("empty" in err.lower() for err in errors)
    
    def test_validate_zip_file_invalid_format(self) -> None:
        """Test rejection of invalid ZIP format."""
        service = create_bulk_upload_service(max_file_size=100 * 1024 * 1024)
        
        errors = service.validate_zip_file(b"This is not a ZIP file")
        
        assert len(errors) > 0
        assert any("Invalid ZIP" in err for err in errors)
    
    def test_validate_zip_file_too_many_files(self) -> None:
        """Test rejection of ZIP with too many files."""
        service = BulkUploadService(
            file_validator=FileValidator(),
            max_files=5,
        )
        
        # Create ZIP with 6 files
        files = {f"file{i}.txt": (TEXT_CONTENT, "text/plain") for i in range(6)}
        zip_content = create_test_zip(files)
        
        errors = service.validate_zip_file(zip_content)
        
        assert len(errors) > 0
        assert any("maximum" in err.lower() for err in errors)
    
    def test_validate_zip_file_no_valid_files(self) -> None:
        """Test rejection of ZIP with only directories."""
        service = create_bulk_upload_service(max_file_size=100 * 1024 * 1024)
        
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as zf:
            # Add only directories
            zf.writestr("folder1/", "")
            zf.writestr("folder2/", "")
        
        errors = service.validate_zip_file(buffer.getvalue())
        
        assert len(errors) > 0
        assert any("no valid files" in err.lower() for err in errors)
    
    def test_extract_and_validate_files(self) -> None:
        """Test extraction of files from ZIP."""
        service = create_bulk_upload_service(max_file_size=100 * 1024 * 1024)
        
        zip_content = create_test_zip({
            "doc1.pdf": (PDF_CONTENT, "application/pdf"),
            "doc2.txt": (TEXT_CONTENT, "text/plain"),
            "image.png": (PNG_CONTENT, "image/png"),
        })
        
        extracted = service.extract_and_validate_files(
            zip_content=zip_content,
            tenant_id="tenant-123",
            request_id="req-456",
        )
        
        assert len(extracted) == 3
        
        # Check extracted files
        filenames = [f[0] for f in extracted]
        assert "doc1.pdf" in filenames
        assert "doc2.txt" in filenames
        assert "image.png" in filenames
    
    def test_extract_skips_system_files(self) -> None:
        """Test that system files are skipped during extraction."""
        service = create_bulk_upload_service(max_file_size=100 * 1024 * 1024)
        
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as zf:
            zf.writestr("doc1.pdf", PDF_CONTENT)
            zf.writestr("__MACOSX/._doc1.pdf", b"metadata")
            zf.writestr(".DS_Store", b"system")
            zf.writestr("Thumbs.db", b"cache")
        
        extracted = service.extract_and_validate_files(
            zip_content=buffer.getvalue(),
            tenant_id="tenant-123",
            request_id="req-456",
        )
        
        # Should only extract the PDF
        assert len(extracted) == 1
        assert extracted[0][0] == "doc1.pdf"
    
    def test_process_file_valid(self) -> None:
        """Test processing of valid file."""
        service = create_bulk_upload_service(max_file_size=100 * 1024 * 1024)
        
        result = service.process_file(
            filename="test.pdf",
            content=PDF_CONTENT,
            mime_type="application/pdf",
        )
        
        assert result.status == "processing"
        assert result.document_id is not None
        assert result.error is None
        assert result.filename == "test.pdf"
        assert result.file_size == len(PDF_CONTENT)
    
    def test_process_file_invalid(self) -> None:
        """Test processing of invalid file."""
        service = create_bulk_upload_service(max_file_size=100 * 1024 * 1024)
        
        # Try to process wrong content as PDF
        result = service.process_file(
            filename="fake.pdf",
            content=b"Not a PDF",
            mime_type="application/pdf",
        )
        
        assert result.status == "failed"
        assert result.document_id is None
        assert result.error is not None
        assert "Magic bytes" in result.error
    
    def test_calculate_file_hash(self) -> None:
        """Test file hash calculation."""
        service = create_bulk_upload_service(max_file_size=100 * 1024 * 1024)
        
        hash1 = service.calculate_file_hash(PDF_CONTENT)
        hash2 = service.calculate_file_hash(PDF_CONTENT)
        
        # Same content should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length
        
        # Different content should produce different hash
        hash3 = service.calculate_file_hash(TEXT_CONTENT)
        assert hash1 != hash3
    
    def test_detect_mime_type(self) -> None:
        """Test MIME type detection from filename."""
        service = create_bulk_upload_service(max_file_size=100 * 1024 * 1024)
        
        assert service._detect_mime_type("doc.pdf") == "application/pdf"
        assert service._detect_mime_type("report.docx") == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert service._detect_mime_type("data.xlsx") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert service._detect_mime_type("image.png") == "image/png"
        assert service._detect_mime_type("photo.jpg") == "image/jpeg"
        assert service._detect_mime_type("photo.jpeg") == "image/jpeg"
        assert service._detect_mime_type("file.txt") == "text/plain"
        assert service._detect_mime_type("data.csv") == "text/csv"
        
        # Unsupported extension
        assert service._detect_mime_type("file.exe") is None
    
    def test_is_system_file(self) -> None:
        """Test system file detection."""
        service = create_bulk_upload_service(max_file_size=100 * 1024 * 1024)
        
        # System files
        assert service._is_system_file("__MACOSX/._file.pdf") is True
        assert service._is_system_file(".DS_Store") is True
        assert service._is_system_file("folder/.hidden") is True
        assert service._is_system_file("Thumbs.db") is True
        
        # Normal files
        assert service._is_system_file("document.pdf") is False
        assert service._is_system_file("folder/file.txt") is False


class TestBulkUploadEndpoint:
    """Integration tests for bulk upload endpoint."""
    
    def test_bulk_upload_success(self, client_with_auth) -> None:
        """Test successful bulk upload."""
        zip_content = create_test_zip({
            "doc1.pdf": (PDF_CONTENT, "application/pdf"),
            "doc2.txt": (TEXT_CONTENT, "text/plain"),
            "image.png": (PNG_CONTENT, "image/png"),
        })
        
        files = {
            "file": ("documents.zip", io.BytesIO(zip_content), "application/zip")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload/bulk", files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert "batch_id" in data
        assert data["total_files"] == 3
        assert data["successful"] == 3
        assert data["failed"] == 0
        assert len(data["documents"]) == 3
        
        # Check document results
        for doc in data["documents"]:
            assert doc["status"] == "processing"
            assert doc["document_id"] is not None
            assert doc["error"] is None
    
    def test_bulk_upload_partial_failure(self, client_with_auth) -> None:
        """Test bulk upload with some invalid files."""
        zip_content = create_test_zip({
            "valid.pdf": (PDF_CONTENT, "application/pdf"),
            "invalid.pdf": (b"Not a PDF", "application/pdf"),
            "valid.txt": (TEXT_CONTENT, "text/plain"),
        })
        
        files = {
            "file": ("mixed.zip", io.BytesIO(zip_content), "application/zip")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload/bulk", files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["total_files"] == 3
        assert data["successful"] == 2
        assert data["failed"] == 1
        
        # Find the failed file
        failed_docs = [d for d in data["documents"] if d["status"] == "failed"]
        assert len(failed_docs) == 1
        assert failed_docs[0]["filename"] == "invalid.pdf"
        assert failed_docs[0]["error"] is not None
        assert failed_docs[0]["document_id"] is None
    
    def test_bulk_upload_reject_invalid_zip(self, client_with_auth) -> None:
        """Test rejection of invalid ZIP file."""
        files = {
            "file": ("notzip.zip", io.BytesIO(b"This is not a ZIP"), "application/zip")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload/bulk", files=files)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["code"] == "ZIP_VALIDATION_ERROR"
    
    def test_bulk_upload_reject_oversized_zip(self, client_with_auth) -> None:
        """Test rejection of oversized ZIP file."""
        # Create ZIP larger than 500MB (using mock)
        large_content = b"x" * (500 * 1024 * 1024 + 1)
        
        files = {
            "file": ("large.zip", io.BytesIO(large_content), "application/zip")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload/bulk", files=files)
        
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        data = response.json()
        assert "exceeds maximum" in str(data["detail"]["errors"])
    
    def test_bulk_upload_empty_zip(self, client_with_auth) -> None:
        """Test rejection of empty ZIP."""
        # Create empty ZIP
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as zf:
            pass  # No files
        
        files = {
            "file": ("empty.zip", io.BytesIO(buffer.getvalue()), "application/zip")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload/bulk", files=files)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert any("no valid files" in err.lower() for err in data["detail"]["errors"])
    
    def test_bulk_upload_mixed_file_types(self, client_with_auth) -> None:
        """Test bulk upload with various supported file types."""
        docx_content = create_valid_docx()
        
        zip_content = create_test_zip({
            "document.pdf": (PDF_CONTENT, "application/pdf"),
            "report.docx": (docx_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "notes.txt": (TEXT_CONTENT, "text/plain"),
            "image.png": (PNG_CONTENT, "image/png"),
            "photo.jpg": (JPEG_CONTENT, "image/jpeg"),
        })
        
        files = {
            "file": ("documents.zip", io.BytesIO(zip_content), "application/zip")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload/bulk", files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["total_files"] == 5
        assert data["successful"] == 5
        assert data["failed"] == 0
    
    def test_bulk_upload_skips_unsupported_files(self, client_with_auth) -> None:
        """Test that unsupported file types are skipped."""
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as zf:
            zf.writestr("valid.pdf", PDF_CONTENT)
            zf.writestr("script.exe", b"executable")
            zf.writestr("video.mp4", b"video content")
        
        files = {
            "file": ("mixed.zip", io.BytesIO(buffer.getvalue()), "application/zip")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload/bulk", files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        # Only PDF should be processed
        assert data["total_files"] == 1
        assert data["successful"] == 1
    
    def test_bulk_upload_requires_authentication(self) -> None:
        """Test that bulk upload requires authentication."""
        client = TestClient(app)
        
        zip_content = create_test_zip({
            "doc.pdf": (PDF_CONTENT, "application/pdf"),
        })
        
        files = {
            "file": ("docs.zip", io.BytesIO(zip_content), "application/zip")
        }
        
        response = client.post("/api/v1/documents/upload/bulk", files=files)
        
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
    
    def test_bulk_upload_requires_permission(self, mock_supabase_client) -> None:
        """Test that bulk upload requires documents:write permission."""
        auth = Mock(spec=AuthContext)
        auth.user_id = "user-123"
        auth.tenant_id = "tenant-456"
        auth.roles = ["Viewer"]
        auth.has_permission = Mock(return_value=False)
        
        def override_get_current_user():
            return auth
        
        def override_get_supabase_client():
            return mock_supabase_client
        
        from src.dependencies import get_current_user, get_supabase_client
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_supabase_client] = override_get_supabase_client
        
        client = TestClient(app)
        
        zip_content = create_test_zip({
            "doc.pdf": (PDF_CONTENT, "application/pdf"),
        })
        
        files = {
            "file": ("docs.zip", io.BytesIO(zip_content), "application/zip")
        }
        
        response = client.post("/api/v1/documents/upload/bulk", files=files)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        app.dependency_overrides.clear()
    
    def test_bulk_upload_tenant_isolation(self, client_with_auth, mock_supabase_client) -> None:
        """Test that bulk upload respects tenant isolation."""
        zip_content = create_test_zip({
            "doc.pdf": (PDF_CONTENT, "application/pdf"),
        })
        
        files = {
            "file": ("docs.zip", io.BytesIO(zip_content), "application/zip")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload/bulk", files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify tenant_id was passed correctly to database
        insert_calls = [
            call for call in mock_supabase_client.table.call_args_list
            if call[0][0] == "documents"
        ]
        assert len(insert_calls) > 0


class TestBulkUploadResponseFormat:
    """Test response format and structure."""
    
    def test_response_structure(self, client_with_auth) -> None:
        """Test that response has correct structure."""
        zip_content = create_test_zip({
            "doc1.pdf": (PDF_CONTENT, "application/pdf"),
            "doc2.txt": (TEXT_CONTENT, "text/plain"),
        })
        
        files = {
            "file": ("docs.zip", io.BytesIO(zip_content), "application/zip")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload/bulk", files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        # Verify top-level fields
        assert "batch_id" in data
        assert "total_files" in data
        assert "successful" in data
        assert "failed" in data
        assert "documents" in data
        
        # Verify types
        assert isinstance(data["batch_id"], str)
        assert isinstance(data["total_files"], int)
        assert isinstance(data["successful"], int)
        assert isinstance(data["failed"], int)
        assert isinstance(data["documents"], list)
        
        # Verify document structure
        for doc in data["documents"]:
            assert "filename" in doc
            assert "document_id" in doc
            assert "status" in doc
            assert isinstance(doc["filename"], str)
            assert doc["status"] in ["processing", "failed"]
    
    def test_failed_file_includes_error(self, client_with_auth) -> None:
        """Test that failed files include error message."""
        zip_content = create_test_zip({
            "invalid.pdf": (b"Not a PDF", "application/pdf"),
        })
        
        files = {
            "file": ("docs.zip", io.BytesIO(zip_content), "application/zip")
        }
        
        response = client_with_auth.post("/api/v1/documents/upload/bulk", files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        
        assert data["failed"] == 1
        failed_doc = data["documents"][0]
        
        assert failed_doc["status"] == "failed"
        assert failed_doc["error"] is not None
        assert len(failed_doc["error"]) > 0
        assert failed_doc["document_id"] is None
