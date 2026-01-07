"""Tests for Supabase-based audit logging."""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

from src.audit.models import AuditLogEntry
from src.audit.supabase_logger import SupabaseAuditLogger


class TestSupabaseAuditLogger:
    """Tests for SupabaseAuditLogger."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock audit config."""
        config = Mock()
        config.audit_retention_years = 7
        config.audit_queue_size = 100
        config.audit_batch_size = 10
        config.audit_flush_interval_seconds = 5
        return config
    
    @pytest.fixture
    def mock_supabase_client(self):
        """Create mock Supabase client."""
        client = Mock()
        table = Mock()
        client.table.return_value = table
        table.insert.return_value.execute.return_value = Mock()
        return client
    
    @pytest.fixture
    def logger(self, mock_config, mock_supabase_client):
        """Create SupabaseAuditLogger instance."""
        with patch('src.audit.supabase_logger.get_audit_config', return_value=mock_config), \
             patch('src.audit.supabase_logger.get_tenant_retention_years', return_value=7):
            return SupabaseAuditLogger(config=mock_config, supabase_client=mock_supabase_client)
    
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
        
        # Verify entry was queued
        assert logger._queue.empty() or logger._batch
    
    @pytest.mark.asyncio
    async def test_write_batch_to_supabase(self, logger):
        """Test writing batch to Supabase."""
        entries = [
            AuditLogEntry.create(
                user_id="auth0|123",
                tenant_id="550e8400-e29b-41d4-a716-446655440000",
                action_type="test.action"
            )
        ]
        
        await logger._write_batch_to_supabase(entries)
        
        # Verify insert was called
        logger.supabase_client.table.assert_called_once_with("audit_logs")
        table = logger.supabase_client.table.return_value
        table.insert.assert_called_once()
        
        # Verify data structure
        call_args = table.insert.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0]["user_id"] == "auth0|123"
        assert call_args[0]["action_type"] == "test.action"
        assert "retention_until" in call_args[0]
    
    def test_log_sync(self, logger):
        """Test synchronous logging."""
        entry = AuditLogEntry.create(
            user_id="auth0|123",
            tenant_id="550e8400-e29b-41d4-a716-446655440000",
            action_type="tampering.attempt"
        )
        
        logger.log_sync(entry)
        
        # Verify insert was called immediately
        logger.supabase_client.table.assert_called_once_with("audit_logs")
        table = logger.supabase_client.table.return_value
        table.insert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, logger):
        """Test error handling during write."""
        entries = [
            AuditLogEntry.create(
                user_id="auth0|123",
                tenant_id="550e8400-e29b-41d4-a716-446655440000",
                action_type="test.action"
            )
        ]
        
        # Simulate Supabase error
        table = logger.supabase_client.table.return_value
        table.insert.return_value.execute.side_effect = Exception("Database error")
        
        with pytest.raises(Exception):
            await logger._write_batch_to_supabase(entries)
