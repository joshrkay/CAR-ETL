"""Property-based tests for audit logging critical paths."""
import pytest
import json
from datetime import datetime
from typing import Dict, Any
from unittest.mock import patch

try:
    from hypothesis import given, strategies as st
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    pytest.skip("hypothesis not available", allow_module_level=True)

from src.audit.models import AuditLogEntry
from src.audit.tampering_detector import detect_and_log_tampering_attempt
from botocore.exceptions import ClientError


class TestAuditLogEntryPropertyBased:
    """Property-based tests for AuditLogEntry model."""
    
    @given(
        user_id=st.text(min_size=1, max_size=255),
        tenant_id=st.text(min_size=1, max_size=255),
        action_type=st.text(min_size=1, max_size=100),
        resource_id=st.one_of(st.none(), st.text(min_size=1, max_size=255))
    )
    def test_entry_creation_with_random_inputs(
        self,
        user_id: str,
        tenant_id: str,
        action_type: str,
        resource_id: str | None
    ):
        """Test that entry creation handles any valid string inputs."""
        entry = AuditLogEntry.create(
            user_id=user_id,
            tenant_id=tenant_id,
            action_type=action_type,
            resource_id=resource_id
        )
        
        assert entry.user_id == user_id
        assert entry.tenant_id == tenant_id
        assert entry.action_type == action_type
        assert entry.resource_id == resource_id
        assert entry.timestamp.endswith("Z")
        assert isinstance(entry.request_metadata, dict)
    
    @given(
        user_id=st.text(min_size=1, max_size=10000),
        tenant_id=st.text(min_size=1, max_size=10000),
        action_type=st.text(min_size=1, max_size=10000)
    )
    def test_entry_json_serialization_with_large_inputs(
        self,
        user_id: str,
        tenant_id: str,
        action_type: str
    ):
        """Test JSON serialization with very large inputs."""
        entry = AuditLogEntry.create(
            user_id=user_id,
            tenant_id=tenant_id,
            action_type=action_type
        )
        
        json_str = entry.to_json()
        assert isinstance(json_str, str)
        
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert parsed["user_id"] == user_id
        assert parsed["tenant_id"] == tenant_id
        assert parsed["action_type"] == action_type
    
    @given(
        user_id=st.text(),
        tenant_id=st.text(),
        action_type=st.text(),
        metadata=st.dictionaries(
            keys=st.text(),
            values=st.one_of(
                st.text(),
                st.integers(),
                st.floats(),
                st.booleans(),
                st.none()
            )
        )
    )
    def test_entry_with_complex_metadata(
        self,
        user_id: str,
        tenant_id: str,
        action_type: str,
        metadata: Dict[str, Any]
    ):
        """Test entry creation with complex nested metadata."""
        entry = AuditLogEntry.create(
            user_id=user_id,
            tenant_id=tenant_id,
            action_type=action_type,
            request_metadata=metadata
        )
        
        assert entry.request_metadata == metadata
        json_str = entry.to_json()
        parsed = json.loads(json_str)
        assert parsed["request_metadata"] == metadata
    
    @given(
        user_id=st.text(),
        tenant_id=st.text(),
        action_type=st.text()
    )
    def test_entry_immutability_property(
        self,
        user_id: str,
        tenant_id: str,
        action_type: str
    ):
        """Test that entries remain immutable after creation."""
        entry = AuditLogEntry.create(
            user_id=user_id,
            tenant_id=tenant_id,
            action_type=action_type
        )
        
        original_user_id = entry.user_id
        original_timestamp = entry.timestamp
        
        # Attempting to modify should raise an exception
        with pytest.raises(Exception):
            entry.user_id = "modified"
        
        # Verify original values unchanged
        assert entry.user_id == original_user_id
        assert entry.timestamp == original_timestamp
    
    @given(
        timestamp_str=st.text()
    )
    def test_timestamp_format_validation(self, timestamp_str: str):
        """Test that timestamps are always in ISO 8601 format."""
        entry = AuditLogEntry.create(
            user_id="test",
            tenant_id="test",
            action_type="test"
        )
        
        # Timestamp should end with Z and be parseable
        assert entry.timestamp.endswith("Z")
        try:
            datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
        except ValueError:
            pytest.fail(f"Timestamp {entry.timestamp} is not valid ISO 8601")


class TestTamperingDetectionPropertyBased:
    """Property-based tests for tampering detection."""
    
    @given(
        error_code=st.one_of(
            st.just("InvalidObjectState"),
            st.just("AccessDenied"),
            st.just("ObjectLockConfigurationNotFoundError"),
            st.text()
        ),
        operation=st.text(),
        s3_key=st.one_of(st.none(), st.text()),
        tenant_id=st.one_of(st.none(), st.text()),
        user_id=st.one_of(st.none(), st.text())
    )
    def test_tampering_detection_with_various_errors(
        self,
        error_code: str,
        operation: str,
        s3_key: str | None,
        tenant_id: str | None,
        user_id: str | None
    ):
        """Test tampering detection handles various error codes."""
        error_response = {
            'Error': {
                'Code': error_code,
                'Message': f"Test error: {error_code}"
            }
        }
        error = ClientError(error_response, operation)
        
        with patch('src.audit.tampering_detector.audit_log_sync') as mock_log:
            detect_and_log_tampering_attempt(
                error=error,
                operation=operation,
                s3_key=s3_key,
                tenant_id=tenant_id,
                user_id=user_id
            )
            
            # Should log if it's a tampering-related error
            is_tampering = error_code in [
                'InvalidObjectState',
                'AccessDenied',
                'ObjectLockConfigurationNotFoundError'
            ]
            
            if is_tampering:
                mock_log.assert_called_once()
                call_args = mock_log.call_args
                assert call_args[1]['action_type'] == "audit.tampering.attempt"
    
    @given(
        error_message=st.text()
    )
    def test_tampering_detection_by_message_content(self, error_message: str):
        """Test tampering detection based on error message content."""
        error_response = {
            'Error': {
                'Code': 'UnknownError',
                'Message': error_message
            }
        }
        error = ClientError(error_response, "TestOperation")
        
        with patch('src.audit.tampering_detector.audit_log_sync') as mock_log:
            detect_and_log_tampering_attempt(
                error=error,
                operation="TestOperation",
                s3_key="test-key"
            )
            
            # Should detect if message contains tampering keywords
            is_tampering = (
                'retention' in error_message.lower() or
                'lock' in error_message.lower()
            )
            
            if is_tampering:
                mock_log.assert_called_once()


class TestAuditLoggingEdgeCases:
    """Property-based tests for edge cases in audit logging."""
    
    @given(
        unicode_text=st.text(
            alphabet=st.characters(
                min_codepoint=0,
                max_codepoint=0x10FFFF,
                blacklist_categories=[]  # Allow all unicode
            ),
            min_size=0,
            max_size=1000
        )
    )
    def test_entry_with_unicode_characters(self, unicode_text: str):
        """Test audit entries handle unicode characters correctly."""
        entry = AuditLogEntry.create(
            user_id=unicode_text,
            tenant_id=unicode_text,
            action_type=unicode_text
        )
        
        # Should serialize and deserialize correctly
        json_str = entry.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["user_id"] == unicode_text
        assert parsed["tenant_id"] == unicode_text
        assert parsed["action_type"] == unicode_text
    
    @given(
        sql_injection_pattern=st.sampled_from([
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "'; SELECT * FROM users; --",
            "1' UNION SELECT NULL--",
            "admin'--",
            "' OR 1=1--"
        ])
    )
    def test_entry_with_sql_injection_patterns(self, sql_injection_pattern: str):
        """Test that SQL injection patterns are safely handled."""
        entry = AuditLogEntry.create(
            user_id=sql_injection_pattern,
            tenant_id=sql_injection_pattern,
            action_type=sql_injection_pattern
        )
        
        # Should serialize without issues
        json_str = entry.to_json()
        parsed = json.loads(json_str)
        
        # Should preserve the pattern (not execute it)
        assert parsed["user_id"] == sql_injection_pattern
        assert sql_injection_pattern in json_str
    
    @given(
        rapid_entries=st.lists(
            st.builds(
                AuditLogEntry.create,
                user_id=st.text(),
                tenant_id=st.text(),
                action_type=st.text()
            ),
            min_size=1,
            max_size=100
        )
    )
    def test_rapid_entry_creation(self, rapid_entries: list[AuditLogEntry]):
        """Test rapid creation of many entries doesn't cause issues."""
        timestamps = [entry.timestamp for entry in rapid_entries]
        
        # All entries should have valid timestamps
        for timestamp in timestamps:
            assert timestamp.endswith("Z")
            try:
                datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                pytest.fail(f"Invalid timestamp: {timestamp}")
        
        # All entries should be serializable
        for entry in rapid_entries:
            json_str = entry.to_json()
            parsed = json.loads(json_str)
            assert parsed["user_id"] == entry.user_id
