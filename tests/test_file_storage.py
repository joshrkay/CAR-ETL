"""
Tests for file storage service.

Tests file upload to Supabase Storage, hash calculation, and error handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4, UUID
from io import BytesIO

from src.services.file_storage import FileStorageService, StorageUploadError


class TestFileStorageService:
    """Unit tests for FileStorageService."""
    
    def test_calculate_file_hash(self) -> None:
        """Test file hash calculation."""
        supabase_mock = Mock()
        service = FileStorageService(supabase_mock)
        
        content = b"test file content"
        hash_value = service.calculate_file_hash(content)
        
        assert len(hash_value) == 64  # SHA-256 hex digest length
        assert isinstance(hash_value, str)
        
        # Same content should produce same hash
        hash_value2 = service.calculate_file_hash(content)
        assert hash_value == hash_value2
        
        # Different content should produce different hash
        different_content = b"different content"
        hash_value3 = service.calculate_file_hash(different_content)
        assert hash_value != hash_value3
    
    def test_calculate_file_hash_empty(self) -> None:
        """Test hash calculation for empty file."""
        supabase_mock = Mock()
        service = FileStorageService(supabase_mock)
        
        hash_value = service.calculate_file_hash(b"")
        
        assert len(hash_value) == 64
        assert isinstance(hash_value, str)
    
    def test_upload_file_success(self) -> None:
        """Test successful file upload."""
        supabase_mock = Mock()
        storage_mock = Mock()
        bucket_mock = Mock()
        
        supabase_mock.storage.from_ = Mock(return_value=bucket_mock)
        bucket_mock.upload = Mock(return_value=None)
        
        service = FileStorageService(supabase_mock)
        
        tenant_id = uuid4()
        content = b"test file content"
        storage_path = "uploads/test/file.txt"
        mime_type = "text/plain"
        
        service.upload_file(
            content=content,
            storage_path=storage_path,
            tenant_id=tenant_id,
            mime_type=mime_type,
        )
        
        # Verify bucket selection
        supabase_mock.storage.from_.assert_called_once_with(f"documents-{tenant_id}")
        
        # Verify upload call
        bucket_mock.upload.assert_called_once()
        call_args = bucket_mock.upload.call_args
        
        assert call_args.kwargs["path"] == storage_path
        assert call_args.kwargs["file_options"]["content-type"] == mime_type
        assert call_args.kwargs["file_options"]["upsert"] == "true"
        assert isinstance(call_args.kwargs["file"], BytesIO)
    
    def test_upload_file_storage_error(self) -> None:
        """Test file upload with storage error."""
        supabase_mock = Mock()
        storage_mock = Mock()
        bucket_mock = Mock()
        
        supabase_mock.storage.from_ = Mock(return_value=bucket_mock)
        bucket_mock.upload = Mock(side_effect=Exception("Storage error"))
        
        service = FileStorageService(supabase_mock)
        
        tenant_id = uuid4()
        content = b"test file content"
        storage_path = "uploads/test/file.txt"
        mime_type = "text/plain"
        
        with pytest.raises(StorageUploadError) as exc_info:
            service.upload_file(
                content=content,
                storage_path=storage_path,
                tenant_id=tenant_id,
                mime_type=mime_type,
            )
        
        assert "Failed to upload file to storage" in str(exc_info.value)
        assert "Storage error" in str(exc_info.value)
    
    def test_upload_file_tenant_isolation(self) -> None:
        """Test that files are uploaded to tenant-specific buckets."""
        supabase_mock = Mock()
        bucket_mock = Mock()
        
        supabase_mock.storage.from_ = Mock(return_value=bucket_mock)
        bucket_mock.upload = Mock(return_value=None)
        
        service = FileStorageService(supabase_mock)
        
        tenant_id_1 = uuid4()
        tenant_id_2 = uuid4()
        content = b"test content"
        
        # Upload to tenant 1
        service.upload_file(
            content=content,
            storage_path="test/file1.txt",
            tenant_id=tenant_id_1,
            mime_type="text/plain",
        )
        
        # Upload to tenant 2
        service.upload_file(
            content=content,
            storage_path="test/file2.txt",
            tenant_id=tenant_id_2,
            mime_type="text/plain",
        )
        
        # Verify different buckets were used
        calls = supabase_mock.storage.from_.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == f"documents-{tenant_id_1}"
        assert calls[1][0][0] == f"documents-{tenant_id_2}"
    
    def test_upload_file_large_content(self) -> None:
        """Test uploading large file content."""
        supabase_mock = Mock()
        bucket_mock = Mock()
        
        supabase_mock.storage.from_ = Mock(return_value=bucket_mock)
        bucket_mock.upload = Mock(return_value=None)
        
        service = FileStorageService(supabase_mock)
        
        tenant_id = uuid4()
        # Create 10MB content
        large_content = b"X" * (10 * 1024 * 1024)
        storage_path = "uploads/large/file.bin"
        
        service.upload_file(
            content=large_content,
            storage_path=storage_path,
            tenant_id=tenant_id,
            mime_type="application/octet-stream",
        )
        
        bucket_mock.upload.assert_called_once()
        call_args = bucket_mock.upload.call_args
        assert isinstance(call_args.kwargs["file"], BytesIO)
        assert call_args.kwargs["file"].getvalue() == large_content
    
    def test_upload_file_mime_type_preserved(self) -> None:
        """Test that MIME type is correctly passed to storage."""
        supabase_mock = Mock()
        bucket_mock = Mock()
        
        supabase_mock.storage.from_ = Mock(return_value=bucket_mock)
        bucket_mock.upload = Mock(return_value=None)
        
        service = FileStorageService(supabase_mock)
        
        tenant_id = uuid4()
        test_cases = [
            ("application/pdf", b"%PDF-1.4"),
            ("image/png", b"\x89PNG\r\n\x1a\n"),
            ("text/plain", b"plain text"),
            ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"PK\x03\x04"),
        ]
        
        for mime_type, content in test_cases:
            bucket_mock.reset_mock()
            
            service.upload_file(
                content=content,
                storage_path=f"test/file.{mime_type.split('/')[-1]}",
                tenant_id=tenant_id,
                mime_type=mime_type,
            )
            
            call_args = bucket_mock.upload.call_args
            assert call_args.kwargs["file_options"]["content-type"] == mime_type
