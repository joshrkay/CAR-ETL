"""Shared test configuration and fixtures."""
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from typing import Generator

# Set up test environment variables before any imports
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key-for-testing")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key-for-testing")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-for-testing")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("LOG_LEVEL", "ERROR")

# Optional environment variables (set to prevent validation errors)
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session", autouse=True)
def mock_rate_limiter() -> Generator[None, None, None]:
    """Mock rate limiter globally for all tests."""
    mock_limiter = Mock()
    mock_limiter.check_rate_limit = Mock(return_value=None)
    mock_limiter.record_attempt = Mock(return_value=None)
    mock_limiter.clear_rate_limit = Mock(return_value=None)

    with patch("src.auth.rate_limit.AuthRateLimiter", return_value=mock_limiter):
        yield


@pytest.fixture(scope="session", autouse=True)
def mock_supabase_create_client() -> Generator[None, None, None]:
    """Mock Supabase client creation globally for all tests."""
    def create_mock_client(*args: any, **kwargs: any) -> Mock:
        """Create a mock Supabase client with proper structure."""
        client = Mock()

        # Mock table method to return properly structured responses
        def mock_table_func(table_name: str) -> Mock:
            table_mock = Mock()
            chain_mock = Mock()
            # Mock the chain methods
            chain_mock.select = Mock(return_value=chain_mock)
            chain_mock.eq = Mock(return_value=chain_mock)
            chain_mock.gte = Mock(return_value=chain_mock)
            chain_mock.order = Mock(return_value=chain_mock)
            chain_mock.limit = Mock(return_value=chain_mock)

            # Mock execute to return empty data (no rate limiting records)
            result_mock = Mock()
            result_mock.data = []  # Empty list means no rate limit records
            chain_mock.execute = Mock(return_value=result_mock)

            return chain_mock

        client.table = Mock(side_effect=mock_table_func)
        client.auth = Mock()
        client.storage = Mock()
        return client

    with patch("src.auth.rate_limit.create_client", side_effect=create_mock_client):
        with patch("supabase.create_client", side_effect=create_mock_client):
            yield


@pytest.fixture(scope="session", autouse=True)
def mock_audit_logger() -> Generator[None, None, None]:
    """Mock audit logger globally for all tests."""
    mock_logger = Mock()
    mock_logger.log_event = Mock(return_value=None)
    mock_logger.flush = Mock(return_value=None)
    mock_logger.log = Mock(return_value=None)
    mock_logger._flush_to_supabase = Mock(return_value=None)

    # Patch AuditLogger class to return our mock
    def create_mock_audit_logger(*args: any, **kwargs: any) -> Mock:
        return mock_logger

    with patch("src.audit.logger.AuditLogger", side_effect=create_mock_audit_logger):
        with patch("src.dependencies.get_audit_logger", return_value=mock_logger):
            yield
