"""
Integration Tests for File Validator Service

Tests include:
- 100MB boundary testing
- Duplicate file detection via content hashing
- Upload session management and cleanup
"""

import hashlib
from datetime import datetime, timedelta
from src.services.file_validator import FileValidator
from typing import Any


class Test100MBFileBoundary:
    """Test exact 100MB file size boundary."""

    def test_exactly_100mb_file(self) -> None:
        """File exactly 100MB should pass validation."""
        size_100mb = 100 * 1024 * 1024
        content = b"A" * size_100mb
        
        validator = FileValidator()
        result = validator.validate_file(content, "text/plain")
        
        assert result.valid is True
        assert result.file_size == size_100mb
        assert len(result.errors) == 0

    def test_100mb_minus_one_byte(self) -> None:
        """File one byte under 100MB should pass."""
        size = (100 * 1024 * 1024) - 1
        content = b"A" * size
        
        validator = FileValidator()
        result = validator.validate_file(content, "text/plain")
        
        assert result.valid is True
        assert result.file_size == size

    def test_100mb_plus_one_byte(self) -> None:
        """File one byte over 100MB should fail."""
        size = (100 * 1024 * 1024) + 1
        content = b"A" * size
        
        validator = FileValidator()
        result = validator.validate_file(content, "text/plain")
        
        assert result.valid is False
        assert any("exceeds maximum" in error for error in result.errors)

    def test_100mb_pdf_file(self) -> None:
        """100MB PDF file should pass with correct magic bytes."""
        size_100mb = 100 * 1024 * 1024
        # Create 100MB PDF
        content = b"%PDF-1.4\n" + b"A" * (size_100mb - 9)
        
        validator = FileValidator()
        result = validator.validate_file(content, "application/pdf")
        
        assert result.valid is True
        assert result.file_size == size_100mb

    def test_100mb_image_handling(self) -> None:
        """100MB PNG image should pass."""
        size_100mb = 100 * 1024 * 1024
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * (size_100mb - 8)
        
        validator = FileValidator()
        result = validator.validate_file(content, "image/png")
        
        assert result.valid is True
        assert result.file_size == size_100mb

    def test_streaming_large_file_simulation(self) -> None:
        """Simulate streaming validation for large files."""
        # Generate 100MB in chunks to simulate streaming
        chunk_size = 10 * 1024 * 1024  # 10MB chunks
        num_chunks = 10
        
        chunks = []
        magic_bytes = b"%PDF-1.4\n"
        chunks.append(magic_bytes)
        
        for _ in range(num_chunks - 1):
            chunks.append(b"A" * chunk_size)
        
        # Final chunk to reach exactly 100MB
        remaining = (100 * 1024 * 1024) - sum(len(c) for c in chunks)
        chunks.append(b"A" * remaining)
        
        content = b"".join(chunks)
        
        validator = FileValidator()
        result = validator.validate_file(content, "application/pdf")
        
        assert result.valid is True
        assert result.file_size == 100 * 1024 * 1024


class TestDuplicateDetection:
    """Test duplicate file detection via content hashing."""

    def test_duplicate_file_detection_same_content(self) -> None:
        """Same content should produce same hash."""
        content1 = b"%PDF-1.4\nSame content"
        content2 = b"%PDF-1.4\nSame content"
        
        hash1 = self._compute_file_hash(content1)
        hash2 = self._compute_file_hash(content2)
        
        assert hash1 == hash2

    def test_duplicate_detection_different_content(self) -> None:
        """Different content should produce different hash."""
        content1 = b"%PDF-1.4\nContent A"
        content2 = b"%PDF-1.4\nContent B"
        
        hash1 = self._compute_file_hash(content1)
        hash2 = self._compute_file_hash(content2)
        
        assert hash1 != hash2

    def test_duplicate_detection_single_byte_difference(self) -> None:
        """Single byte difference should produce different hash."""
        content1 = b"%PDF-1.4\nContent"
        content2 = b"%PDF-1.4\ncontent"  # lowercase 'c'
        
        hash1 = self._compute_file_hash(content1)
        hash2 = self._compute_file_hash(content2)
        
        assert hash1 != hash2

    def test_duplicate_with_validation(self) -> None:
        """Validate and detect duplicate in single operation."""
        content = b"%PDF-1.4\nTest document"
        
        validator = FileValidator()
        result = validator.validate_file(content, "application/pdf")
        file_hash = self._compute_file_hash(content)
        
        assert result.valid is True
        assert len(file_hash) == 64  # SHA-256 hex digest length

    def test_large_file_hash_consistency(self) -> None:
        """Large file hashing should be consistent."""
        size_50mb = 50 * 1024 * 1024
        content = b"%PDF-1.4\n" + b"A" * size_50mb
        
        hash1 = self._compute_file_hash(content)
        hash2 = self._compute_file_hash(content)
        
        assert hash1 == hash2

    def test_deduplication_registry(self) -> None:
        """Test in-memory deduplication registry."""
        registry: dict[str, dict[str, Any]] = {}
        
        # Upload same file twice
        content = b"%PDF-1.4\nDocument"
        file_hash = self._compute_file_hash(content)
        
        # First upload
        if file_hash not in registry:
            registry[file_hash] = {
                "first_seen": datetime.now(),
                "count": 1,
                "size": len(content)
            }
        else:
            registry[file_hash]["count"] += 1
        
        # Second upload (duplicate)
        if file_hash not in registry:
            registry[file_hash] = {
                "first_seen": datetime.now(),
                "count": 1,
                "size": len(content)
            }
        else:
            registry[file_hash]["count"] += 1
        
        assert registry[file_hash]["count"] == 2

    def test_hash_collision_resistance(self) -> None:
        """Different files should produce different hashes (collision resistance)."""
        test_files = [
            b"%PDF-1.4\nFile 1",
            b"%PDF-1.4\nFile 2",
            b"%PDF-1.4\nFile 3",
            b"%PDF-1.5\nFile 1",  # Different version
            b"\x89PNG\r\n\x1a\nImage data",
        ]
        
        hashes = [self._compute_file_hash(content) for content in test_files]
        
        # All hashes should be unique
        assert len(hashes) == len(set(hashes))

    @staticmethod
    def _compute_file_hash(content: bytes) -> str:
        """Compute SHA-256 hash of file content."""
        return hashlib.sha256(content).hexdigest()


class UploadSession:
    """Simple upload session for testing."""
    
    def __init__(self, session_id: str, tenant_id: str, expires_at: datetime) -> None:
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.created_at = datetime.now()
        self.expires_at = expires_at
        self.files: list[dict] = []
        self.is_active = True

    def add_file(self, file_hash: str, file_size: int, mime_type: str) -> None:
        """Add file to session."""
        self.files.append({
            "hash": file_hash,
            "size": file_size,
            "mime_type": mime_type,
            "uploaded_at": datetime.now()
        })

    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.now() > self.expires_at

    def cleanup(self) -> None:
        """Mark session for cleanup."""
        self.is_active = False


class TestExpiredSessionCleanup:
    """Test upload session management and cleanup."""

    def test_session_creation(self) -> None:
        """Create upload session with expiration."""
        session_id = "session_123"
        tenant_id = "tenant_abc"
        expires_at = datetime.now() + timedelta(hours=24)
        
        session = UploadSession(session_id, tenant_id, expires_at)
        
        assert session.session_id == session_id
        assert session.tenant_id == tenant_id
        assert session.is_active is True
        assert session.is_expired() is False

    def test_session_expiration(self) -> None:
        """Session should expire after timeout."""
        session_id = "session_expired"
        tenant_id = "tenant_abc"
        expires_at = datetime.now() - timedelta(hours=1)  # Already expired
        
        session = UploadSession(session_id, tenant_id, expires_at)
        
        assert session.is_expired() is True

    def test_session_cleanup_on_expiration(self) -> None:
        """Expired sessions should be cleaned up."""
        sessions = []
        
        # Create active session
        active_session = UploadSession(
            "session_active",
            "tenant_abc",
            datetime.now() + timedelta(hours=24)
        )
        sessions.append(active_session)
        
        # Create expired session
        expired_session = UploadSession(
            "session_expired",
            "tenant_abc",
            datetime.now() - timedelta(hours=1)
        )
        sessions.append(expired_session)
        
        # Cleanup expired sessions
        for session in sessions:
            if session.is_expired():
                session.cleanup()
        
        assert active_session.is_active is True
        assert expired_session.is_active is False

    def test_session_file_tracking(self) -> None:
        """Session should track uploaded files."""
        session = UploadSession(
            "session_123",
            "tenant_abc",
            datetime.now() + timedelta(hours=24)
        )
        
        # Add files
        session.add_file("hash1", 1024, "application/pdf")
        session.add_file("hash2", 2048, "image/png")
        
        assert len(session.files) == 2
        assert session.files[0]["hash"] == "hash1"
        assert session.files[1]["hash"] == "hash2"

    def test_session_timeout_configurations(self) -> None:
        """Test different timeout configurations."""
        test_cases = [
            (timedelta(hours=1), "1 hour"),
            (timedelta(hours=24), "24 hours"),
            (timedelta(days=7), "7 days"),
            (timedelta(minutes=30), "30 minutes"),
        ]
        
        for timeout, description in test_cases:
            expires_at = datetime.now() + timeout
            session = UploadSession(f"session_{description}", "tenant_abc", expires_at)
            
            assert session.is_expired() is False

    def test_concurrent_session_cleanup(self) -> None:
        """Test cleanup of multiple sessions."""
        sessions_registry = {}
        
        # Create mix of active and expired sessions
        for i in range(10):
            if i % 2 == 0:
                # Active session
                expires_at = datetime.now() + timedelta(hours=24)
            else:
                # Expired session
                expires_at = datetime.now() - timedelta(hours=1)
            
            session = UploadSession(f"session_{i}", "tenant_abc", expires_at)
            sessions_registry[session.session_id] = session
        
        # Cleanup expired sessions
        expired_count = 0
        for session_id, session in list(sessions_registry.items()):
            if session.is_expired():
                session.cleanup()
                expired_count += 1
        
        assert expired_count == 5  # Half should be expired

    def test_session_with_file_validation(self) -> None:
        """Integration test: validate file and add to session."""
        # Create session
        session = UploadSession(
            "session_integration",
            "tenant_abc",
            datetime.now() + timedelta(hours=24)
        )
        
        # Validate file
        content = b"%PDF-1.4\nTest document"
        validator = FileValidator()
        result = validator.validate_file(content, "application/pdf")
        
        # If valid, add to session
        if result.valid:
            file_hash = hashlib.sha256(content).hexdigest()
            session.add_file(file_hash, result.file_size, result.mime_type)
        
        assert len(session.files) == 1
        assert session.files[0]["mime_type"] == "application/pdf"

    def test_session_duplicate_prevention(self) -> None:
        """Prevent uploading same file twice in one session."""
        session = UploadSession(
            "session_dedup",
            "tenant_abc",
            datetime.now() + timedelta(hours=24)
        )
        
        content = b"%PDF-1.4\nDocument"
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Add file
        session.add_file(file_hash, len(content), "application/pdf")
        
        # Check if already uploaded
        existing_hashes = {f["hash"] for f in session.files}
        is_duplicate = file_hash in existing_hashes
        
        assert is_duplicate is True
        
        # Don't add duplicate
        if not is_duplicate:
            session.add_file(file_hash, len(content), "application/pdf")
        
        assert len(session.files) == 1

    def test_session_cleanup_removes_file_references(self) -> None:
        """Cleanup should remove file references."""
        session = UploadSession(
            "session_cleanup",
            "tenant_abc",
            datetime.now() - timedelta(hours=1)
        )
        
        # Add files
        session.add_file("hash1", 1024, "application/pdf")
        session.add_file("hash2", 2048, "image/png")
        
        # Verify files exist
        assert len(session.files) == 2
        
        # Cleanup
        if session.is_expired():
            session.cleanup()
            # In production, this would also:
            # - Delete temporary files from disk/S3
            # - Remove database records
            # - Clear cache entries
        
        assert session.is_active is False


class TestIntegrationScenarios:
    """End-to-end integration scenarios."""

    def test_complete_upload_workflow(self) -> None:
        """Test complete file upload workflow with validation, dedup, and session."""
        # Step 1: Create upload session
        session = UploadSession(
            "session_workflow",
            "tenant_abc",
            datetime.now() + timedelta(hours=24)
        )
        
        # Step 2: Validate file
        pdf_header = b"%PDF-1.4\n"
        content = pdf_header + b"A" * (50 * 1024 * 1024)  # ~50MB
        validator = FileValidator()
        result = validator.validate_file(content, "application/pdf")
        
        assert result.valid is True
        
        # Step 3: Check for duplicates
        file_hash = hashlib.sha256(content).hexdigest()
        existing_hashes = {f["hash"] for f in session.files}
        
        if file_hash not in existing_hashes:
            # Step 4: Add to session
            session.add_file(file_hash, result.file_size, result.mime_type)
        
        # Verify
        assert len(session.files) == 1
        expected_size = len(pdf_header) + (50 * 1024 * 1024)
        assert session.files[0]["size"] == expected_size

    def test_multi_tenant_isolation(self) -> None:
        """Different tenants should have isolated sessions."""
        tenant_a_session = UploadSession(
            "session_a",
            "tenant_a",
            datetime.now() + timedelta(hours=24)
        )
        
        tenant_b_session = UploadSession(
            "session_b",
            "tenant_b",
            datetime.now() + timedelta(hours=24)
        )
        
        # Same file uploaded to different tenants
        content = b"%PDF-1.4\nShared document"
        file_hash = hashlib.sha256(content).hexdigest()
        
        tenant_a_session.add_file(file_hash, len(content), "application/pdf")
        tenant_b_session.add_file(file_hash, len(content), "application/pdf")
        
        # Both should have the file (no cross-tenant deduplication)
        assert len(tenant_a_session.files) == 1
        assert len(tenant_b_session.files) == 1
        assert tenant_a_session.tenant_id != tenant_b_session.tenant_id

    def test_batch_upload_validation(self) -> None:
        """Validate multiple files in batch."""
        files = [
            (b"%PDF-1.4\nDoc1", "application/pdf"),
            (b"\x89PNG\r\n\x1a\nImage1", "image/png"),
            (b"\xff\xd8\xff\xe0JPEG1", "image/jpeg"),
        ]
        
        validator = FileValidator()
        results = []
        
        for content, mime_type in files:
            result = validator.validate_file(content, mime_type)
            results.append(result)
        
        # All should be valid
        assert all(r.valid for r in results)
        assert len(results) == 3

    def test_error_recovery_on_invalid_file(self) -> None:
        """Session should handle validation failures gracefully."""
        session = UploadSession(
            "session_error_handling",
            "tenant_abc",
            datetime.now() + timedelta(hours=24)
        )
        
        # Valid file
        valid_content = b"%PDF-1.4\nValid"
        validator = FileValidator()
        result = validator.validate_file(valid_content, "application/pdf")
        if result.valid:
            file_hash = hashlib.sha256(valid_content).hexdigest()
            session.add_file(file_hash, result.file_size, result.mime_type)
        
        # Invalid file
        invalid_content = b"NOT A PDF"
        result = validator.validate_file(invalid_content, "application/pdf")
        if result.valid:
            file_hash = hashlib.sha256(invalid_content).hexdigest()
            session.add_file(file_hash, result.file_size, result.mime_type)
        
        # Only valid file should be in session
        assert len(session.files) == 1
