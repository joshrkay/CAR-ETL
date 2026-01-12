"""Tests for authentication rate limiting."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from src.auth.rate_limit import AuthRateLimiter, get_rate_limiter
from src.auth.config import AuthConfig
from src.exceptions import RateLimitError


from typing import Any, Generator
@pytest.fixture
def mock_config() -> Any:
    """Create mock auth config."""
    config = Mock(spec=AuthConfig)
    config.supabase_url = "https://test.supabase.co"
    config.supabase_service_key = "test-key"
    config.auth_rate_limit_max_attempts = 5
    config.auth_rate_limit_window_seconds = 300
    config.is_production = False
    return config


@pytest.fixture
def mock_supabase() -> Any:
    """Create mock Supabase client."""
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    return mock_client


class TestAuthRateLimiter:
    """Test authentication rate limiter."""

    def test_first_attempt_creates_new_record(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test that first attempt from IP creates new rate limit record."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)

            # Mock no existing records
            mock_execute = MagicMock()
            mock_execute.data = []
            mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = (
                mock_execute
            )

            # Should not raise
            limiter.check_rate_limit("192.168.1.1")

            # Verify insert was called
            mock_supabase.table.return_value.insert.assert_called_once()
            call_args = mock_supabase.table.return_value.insert.call_args[0][0]
            assert call_args["ip_address"] == "192.168.1.1"
            assert call_args["attempt_count"] == 1

    def test_subsequent_attempts_increment_count(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test that subsequent attempts increment the attempt count."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)

            # Mock existing record with 2 attempts
            mock_execute = MagicMock()
            mock_execute.data = [
                {
                    "id": "record-123",
                    "ip_address": "192.168.1.1",
                    "attempt_count": 2,
                    "window_start": datetime.utcnow().isoformat(),
                }
            ]
            mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = (
                mock_execute
            )

            # Should not raise (under limit)
            limiter.check_rate_limit("192.168.1.1")

            # Verify update was called with incremented count
            mock_supabase.table.return_value.update.assert_called_once()
            call_args = mock_supabase.table.return_value.update.call_args[0][0]
            assert call_args["attempt_count"] == 3

    def test_rate_limit_exceeded_raises_error(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test that exceeding rate limit raises RateLimitError."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)

            # Mock existing record at max attempts
            now = datetime.utcnow()
            mock_execute = MagicMock()
            mock_execute.data = [
                {
                    "id": "record-123",
                    "ip_address": "192.168.1.1",
                    "attempt_count": 5,  # At max
                    "window_start": now.isoformat(),
                }
            ]
            mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = (
                mock_execute
            )

            # Should raise RateLimitError
            with pytest.raises(RateLimitError) as exc_info:
                limiter.check_rate_limit("192.168.1.1")

            assert exc_info.value.retry_after > 0

    def test_rate_limit_retry_after_calculation(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test that retry_after is calculated correctly."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)

            # Mock record at max attempts from 100 seconds ago
            window_start = datetime.utcnow() - timedelta(seconds=100)
            mock_execute = MagicMock()
            mock_execute.data = [
                {
                    "id": "record-123",
                    "ip_address": "192.168.1.1",
                    "attempt_count": 5,
                    "window_start": window_start.isoformat(),
                }
            ]
            mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = (
                mock_execute
            )

            with pytest.raises(RateLimitError) as exc_info:
                limiter.check_rate_limit("192.168.1.1")

            # retry_after should be approximately 200 seconds (300 - 100)
            assert 190 <= exc_info.value.retry_after <= 210

    def test_window_start_with_timezone(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test handling of window_start with timezone suffix."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)

            # Mock record with timezone in window_start
            window_start = datetime.utcnow() - timedelta(seconds=50)
            mock_execute = MagicMock()
            mock_execute.data = [
                {
                    "id": "record-123",
                    "ip_address": "192.168.1.1",
                    "attempt_count": 5,
                    "window_start": window_start.isoformat() + "Z",  # With Z suffix
                }
            ]
            mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = (
                mock_execute
            )

            with pytest.raises(RateLimitError) as exc_info:
                limiter.check_rate_limit("192.168.1.1")

            # Should still calculate retry_after correctly
            assert exc_info.value.retry_after > 0

    def test_reset_rate_limit(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test resetting rate limit for an IP address."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)

            limiter.reset_rate_limit("192.168.1.1")

            # Verify delete was called
            mock_supabase.table.return_value.delete.return_value.eq.assert_called_once()

    def test_error_handling_in_non_production(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test that errors are suppressed in non-production mode."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)
            mock_config.is_production = False

            # Mock database error
            mock_supabase.table.return_value.select.side_effect = Exception(
                "Database error"
            )

            # Should not raise in non-production
            limiter.check_rate_limit("192.168.1.1")

    def test_error_handling_in_production(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test that errors are raised in production mode."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)
            mock_config.is_production = True

            # Mock database error
            mock_supabase.table.return_value.select.side_effect = Exception(
                "Database error"
            )

            # Should raise in production
            with pytest.raises(Exception, match="Database error"):
                limiter.check_rate_limit("192.168.1.1")

    def test_increment_attempt_error_handling(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test error handling in _increment_attempt."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)

            # Mock existing record
            mock_execute = MagicMock()
            mock_execute.data = [
                {
                    "id": "record-123",
                    "ip_address": "192.168.1.1",
                    "attempt_count": 2,
                    "window_start": datetime.utcnow().isoformat(),
                }
            ]
            mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = (
                mock_execute
            )

            # Mock update error (non-production)
            mock_config.is_production = False
            mock_supabase.table.return_value.update.side_effect = Exception(
                "Update error"
            )

            # Should not raise in non-production
            limiter.check_rate_limit("192.168.1.1")

    def test_create_record_error_handling(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test error handling in _create_new_record."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)
            mock_config.is_production = False

            # Mock no existing records
            mock_execute = MagicMock()
            mock_execute.data = []
            mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = (
                mock_execute
            )

            # Mock insert error
            mock_supabase.table.return_value.insert.side_effect = Exception(
                "Insert error"
            )

            # Should not raise in non-production
            limiter.check_rate_limit("192.168.1.1")

    def test_reset_error_handling_production(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test error handling in reset_rate_limit in production."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)
            mock_config.is_production = True

            # Mock delete error
            mock_supabase.table.return_value.delete.side_effect = Exception(
                "Delete error"
            )

            # Should raise in production
            with pytest.raises(Exception, match="Delete error"):
                limiter.reset_rate_limit("192.168.1.1")

    def test_reset_error_handling_non_production(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test error handling in reset_rate_limit in non-production."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)
            mock_config.is_production = False

            # Mock delete error
            mock_supabase.table.return_value.delete.side_effect = Exception(
                "Delete error"
            )

            # Should not raise in non-production
            limiter.reset_rate_limit("192.168.1.1")

    def test_get_rate_limiter(self) -> None:
        """Test get_rate_limiter factory function."""
        with patch("src.auth.rate_limit.get_auth_config") as mock_get_config:
            mock_config = Mock(spec=AuthConfig)
            mock_config.supabase_url = "https://test.supabase.co"
            mock_config.supabase_service_key = "test-key"
            mock_get_config.return_value = mock_config

            with patch("src.auth.rate_limit.create_client"):
                limiter = get_rate_limiter()
                assert isinstance(limiter, AuthRateLimiter)
                assert limiter.config == mock_config

    def test_rate_limit_window_expiry(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test that old records outside the window are ignored."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)

            # Mock no records within current window
            mock_execute = MagicMock()
            mock_execute.data = []
            mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = (
                mock_execute
            )

            # Should create new record (not raise)
            limiter.check_rate_limit("192.168.1.1")

            # Verify insert was called (starting fresh count)
            assert mock_supabase.table.return_value.insert.called

    def test_rate_limit_error_propagates(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test that RateLimitError is always propagated even in non-production."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)
            mock_config.is_production = False

            # Mock record at max attempts
            mock_execute = MagicMock()
            mock_execute.data = [
                {
                    "id": "record-123",
                    "ip_address": "192.168.1.1",
                    "attempt_count": 5,
                    "window_start": datetime.utcnow().isoformat(),
                }
            ]
            mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = (
                mock_execute
            )

            # RateLimitError should always propagate
            with pytest.raises(RateLimitError):
                limiter.check_rate_limit("192.168.1.1")

    def test_attempt_count_none_defaults_to_zero(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test that None attempt_count defaults to 0."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)

            # Mock record with None attempt_count
            mock_execute = MagicMock()
            mock_execute.data = [
                {
                    "id": "record-123",
                    "ip_address": "192.168.1.1",
                    "attempt_count": None,  # None value
                    "window_start": datetime.utcnow().isoformat(),
                }
            ]
            mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = (
                mock_execute
            )

            # Should not raise (defaults to 0)
            limiter.check_rate_limit("192.168.1.1")

            # Verify update was called with incremented count from 0
            mock_supabase.table.return_value.update.assert_called_once()
            call_args = mock_supabase.table.return_value.update.call_args[0][0]
            assert call_args["attempt_count"] == 1

    def test_attempt_count_invalid_string_defaults_to_zero(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test that invalid string attempt_count defaults to 0."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)

            # Mock record with invalid string attempt_count
            mock_execute = MagicMock()
            mock_execute.data = [
                {
                    "id": "record-123",
                    "ip_address": "192.168.1.1",
                    "attempt_count": "invalid",  # Non-numeric string
                    "window_start": datetime.utcnow().isoformat(),
                }
            ]
            mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = (
                mock_execute
            )

            # Should not raise (defaults to 0)
            limiter.check_rate_limit("192.168.1.1")

            # Verify update was called with incremented count from 0
            mock_supabase.table.return_value.update.assert_called_once()
            call_args = mock_supabase.table.return_value.update.call_args[0][0]
            assert call_args["attempt_count"] == 1

    def test_attempt_count_numeric_string_converts_correctly(self, mock_config: Any, mock_supabase: Any) -> None:
        """Test that numeric string attempt_count is converted correctly."""
        with patch("src.auth.rate_limit.create_client", return_value=mock_supabase):
            limiter = AuthRateLimiter(mock_config)

            # Mock record with numeric string attempt_count
            mock_execute = MagicMock()
            mock_execute.data = [
                {
                    "id": "record-123",
                    "ip_address": "192.168.1.1",
                    "attempt_count": "3",  # Numeric string
                    "window_start": datetime.utcnow().isoformat(),
                }
            ]
            mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = (
                mock_execute
            )

            # Should not raise
            limiter.check_rate_limit("192.168.1.1")

            # Verify update was called with incremented count from 3
            mock_supabase.table.return_value.update.assert_called_once()
            call_args = mock_supabase.table.return_value.update.call_args[0][0]
            assert call_args["attempt_count"] == 4
