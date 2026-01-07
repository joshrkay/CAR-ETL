"""Tests for immutable audit logging."""
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

from src.audit.models import AuditLogEntry
from src.audit.s3_logger import S3AuditLogger
from src.audit.service import audit_log, audit_log_sync


class TestAuditLogEntry:
    """Tests for AuditLogEntry model."""
    
    def test_create_entry(self):
        """Test creating an audit log entry."""
        entry = AuditLogEntry.create(
            user_id="auth0|123",
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            action_type="document.upload",
            resource_id="doc-456"
        )
        
        assert entry.user_id == "auth0|123"
        assert entry.tenant_id == "550e8400-e29b-41d4-a716-446655440000"
        assert entry.action_type == "document.upload"
        assert entry.resource_id == "doc-456"
        assert entry.timestamp.endswith("Z")
        assert isinstance(entry.request_metadata, dict)
    
    def test_entry_immutable(self):
        """Test that entry is immutable after creation."""
        entry = AuditLogEntry.create(
            user_id="auth0|123",
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            action_type="test.action"
        )
        
        # Pydantic frozen models raise ValidationError on modification
        with pytest.raises(Exception):
            entry.user_id = "new_user"
    
    def test_to_json(self):
        """Test JSON serialization."""
        entry = AuditLogEntry.create(
            user_id="auth0|123",
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            action_type="test.action"
        )
        
        json_str = entry.to_json()
        assert isinstance(json_str, str)
        
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert parsed["user_id"] == "auth0|123"
        assert parsed["action_type"] == "test.action"


class TestS3AuditLogger:
    """Tests for S3AuditLogger."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock audit config."""
        config = Mock()
        config.audit_s3_bucket = "test-audit-bucket"
        config.audit_s3_region = "us-east-1"
        config.audit_retention_years = 7
        config.audit_queue_size = 100
        config.audit_batch_size = 10
        config.audit_flush_interval_seconds = 5
        config.aws_access_key_id = None
        config.aws_secret_access_key = None
        return config
    
    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        client = Mock()
        client.put_object = Mock()
        return client
    
    @pytest.fixture
    def logger(self, mock_config, mock_s3_client):
        """Create S3AuditLogger instance."""
        with patch('src.audit.s3_logger.get_audit_config', return_value=mock_config):
            return S3AuditLogger(config=mock_config, s3_client=mock_s3_client)
    
    @pytest.mark.asyncio
    async def test_log_entry(self, logger):
        """Test logging an entry."""
        entry = AuditLogEntry.create(
            user_id="auth0|123",
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            action_type="test.action"
        )
        
        await logger.start()
        await logger.log(entry)
        await logger.stop()
        
        # Verify entry was queued (would be written in flush)
        assert logger._queue.empty() or logger._batch
    
    @pytest.mark.asyncio
    async def test_write_batch_to_s3(self, logger):
        """Test writing batch to S3."""
        entries = [
            AuditLogEntry.create(
                user_id="auth0|123",
                tenant_id="550e8400-e29b-41d4-a716-446655440000",
                action_type="test.action"
            )
        ]
        
        await logger._write_batch_to_s3(entries)
        
        # Verify put_object was called
        logger.s3_client.put_object.assert_called_once()
        call_args = logger.s3_client.put_object.call_args
        
        assert call_args[1]['Bucket'] == "test-audit-bucket"
        assert call_args[1]['ObjectLockMode'] == 'COMPLIANCE'
        assert 'Key' in call_args[1]
    
    def test_log_sync(self, logger):
        """Test synchronous logging."""
        entry = AuditLogEntry.create(
            user_id="auth0|123",
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            action_type="tampering.attempt"
        )
        
        logger.log_sync(entry)
        
        # Verify put_object was called immediately
        logger.s3_client.put_object.assert_called_once()
        call_args = logger.s3_client.put_object.call_args
        
        assert call_args[1]['Bucket'] == "test-audit-bucket"
        assert call_args[1]['ObjectLockMode'] == 'COMPLIANCE'


class TestAuditService:
    """Tests for audit service functions."""
    
    @pytest.mark.asyncio
    async def test_audit_log(self):
        """Test async audit logging."""
        mock_logger = Mock()
        mock_logger.log = AsyncMock()
        
        with patch('src.audit.service.get_audit_logger', return_value=mock_logger):
            await audit_log(
                user_id="auth0|123",
                tenant_id="550e8400-e29b-41d4-a716-446655440000",
                action_type="test.action"
            )
            
            mock_logger.log.assert_called_once()
            entry = mock_logger.log.call_args[0][0]
            assert isinstance(entry, AuditLogEntry)
            assert entry.user_id == "auth0|123"
            assert entry.action_type == "test.action"
    
    def test_audit_log_sync(self):
        """Test synchronous audit logging."""
        mock_logger = Mock()
        mock_logger.log_sync = Mock()
        
        with patch('src.audit.service.get_audit_logger', return_value=mock_logger):
            audit_log_sync(
                user_id="auth0|123",
                tenant_id="550e8400-e29b-41d4-a716-446655440000",
                action_type="tampering.attempt"
            )
            
            mock_logger.log_sync.assert_called_once()
            entry = mock_logger.log_sync.call_args[0][0]
            assert isinstance(entry, AuditLogEntry)
            assert entry.action_type == "tampering.attempt"
