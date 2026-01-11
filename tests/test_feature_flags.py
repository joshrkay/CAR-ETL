"""Unit tests for feature flag system."""
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.features.service import FeatureFlagService, _shared_cache


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client."""
    client = Mock()
    client.table = Mock(return_value=client)
    client.select = Mock(return_value=client)
    client.eq = Mock(return_value=client)
    client.limit = Mock(return_value=client)
    client.order = Mock(return_value=client)
    client.insert = Mock(return_value=client)
    client.update = Mock(return_value=client)
    client.delete = Mock(return_value=client)
    client.execute = Mock(return_value=Mock(data=[]))
    return client


@pytest.fixture
def tenant_id():
    """Create a test tenant ID."""
    return uuid4()


@pytest.fixture
def flag_service(mock_supabase_client, tenant_id):
    """Create a FeatureFlagService instance."""
    # Clear the shared cache before each test
    _shared_cache.clear()
    return FeatureFlagService(mock_supabase_client, tenant_id)


@pytest.mark.asyncio
async def test_is_enabled_flag_exists_with_default(flag_service, mock_supabase_client) -> None:
    """Test is_enabled when flag exists with default value."""
    flag_id = uuid4()

    # Mock flag lookup
    flag_result = Mock(data=[{"id": str(flag_id), "name": "test_flag", "enabled_default": True}])

    # Mock tenant override lookup (no override)
    override_result = Mock(data=[])

    call_count = {"count": 0}

    def execute_side_effect():
        call_count["count"] += 1
        if call_count["count"] == 1:
            # First call: flag lookup
            return flag_result
        else:
            # Second call: tenant override lookup
            return override_result

    mock_supabase_client.execute.side_effect = execute_side_effect

    result = await flag_service.is_enabled("test_flag")

    assert result is True
    cache_key = (flag_service.tenant_id, "test_flag")
    assert cache_key in _shared_cache


@pytest.mark.asyncio
async def test_is_enabled_flag_exists_with_override(flag_service, mock_supabase_client) -> None:
    """Test is_enabled when flag exists with tenant override."""
    flag_id = uuid4()

    # Mock flag lookup
    flag_result = Mock(data=[{"id": str(flag_id), "name": "test_flag", "enabled_default": False}])

    # Mock tenant override lookup
    override_result = Mock(data=[{"enabled": True}])

    call_count = {"count": 0}

    def execute_side_effect():
        call_count["count"] += 1
        if call_count["count"] == 1:
            return flag_result
        else:
            return override_result

    mock_supabase_client.execute.side_effect = execute_side_effect

    result = await flag_service.is_enabled("test_flag")

    assert result is True  # Override enabled=True overrides default False
    cache_key = (flag_service.tenant_id, "test_flag")
    assert cache_key in _shared_cache


@pytest.mark.asyncio
async def test_is_enabled_flag_not_exists(flag_service, mock_supabase_client) -> None:
    """Test is_enabled when flag doesn't exist."""
    mock_supabase_client.execute.return_value = Mock(data=[])

    result = await flag_service.is_enabled("nonexistent_flag")

    assert result is False
    cache_key = (flag_service.tenant_id, "nonexistent_flag")
    assert cache_key in _shared_cache


@pytest.mark.asyncio
async def test_is_enabled_uses_cache(flag_service, mock_supabase_client) -> None:
    """Test that is_enabled uses cache when valid."""
    uuid4()

    # Set up cache with TTLCache
    cache_key = (flag_service.tenant_id, "test_flag")
    _shared_cache[cache_key] = True

    # Should not call execute if cache is valid
    result = await flag_service.is_enabled("test_flag")

    assert result is True
    # Verify execute was not called (cache was used)
    mock_supabase_client.execute.assert_not_called()


@pytest.mark.asyncio
async def test_is_enabled_cache_expired(flag_service, mock_supabase_client) -> None:
    """Test that is_enabled refreshes cache when expired (TTL expired automatically)."""
    flag_id = uuid4()

    # Note: With TTLCache, we can't manually set expired entries.
    # This test verifies that a fresh lookup occurs when cache is empty.

    # Mock flag lookup
    flag_result = Mock(data=[{"id": str(flag_id), "name": "test_flag", "enabled_default": True}])

    # Mock tenant override lookup (no override)
    override_result = Mock(data=[])

    call_count = {"count": 0}

    def execute_side_effect():
        call_count["count"] += 1
        if call_count["count"] == 1:
            return flag_result
        else:
            return override_result

    mock_supabase_client.execute.side_effect = execute_side_effect

    result = await flag_service.is_enabled("test_flag")

    assert result is True  # Fresh lookup returns True
    cache_key = (flag_service.tenant_id, "test_flag")
    assert _shared_cache[cache_key] is True  # Cache updated


@pytest.mark.asyncio
async def test_get_all_flags(flag_service, mock_supabase_client) -> None:
    """Test get_all_flags returns all flags with tenant overrides."""
    flag1_id = uuid4()
    flag2_id = uuid4()

    # Mock flags lookup
    flags_result = Mock(
        data=[
            {"id": str(flag1_id), "name": "flag1", "enabled_default": False},
            {"id": str(flag2_id), "name": "flag2", "enabled_default": True},
        ]
    )

    # Mock tenant overrides
    overrides_result = Mock(data=[{"flag_id": str(flag1_id), "enabled": True}])

    call_count = {"count": 0}

    def execute_side_effect():
        call_count["count"] += 1
        if call_count["count"] == 1:
            return flags_result
        else:
            return overrides_result

    mock_supabase_client.execute.side_effect = execute_side_effect

    result = await flag_service.get_all_flags()

    assert result == {
        "flag1": True,  # Override enabled=True
        "flag2": True,  # Default enabled=True
    }
    cache_key1 = (flag_service.tenant_id, "flag1")
    cache_key2 = (flag_service.tenant_id, "flag2")
    assert cache_key1 in _shared_cache
    assert cache_key2 in _shared_cache


@pytest.mark.asyncio
async def test_get_flag_details(flag_service, mock_supabase_client) -> None:
    """Test get_flag_details returns detailed flag information."""
    flag_id = uuid4()

    # Mock flag lookup
    flag_result = Mock(
        data=[{
            "id": str(flag_id),
            "name": "test_flag",
            "description": "Test flag description",
            "enabled_default": False,
        }]
    )

    # Mock tenant override
    override_result = Mock(data=[{"enabled": True}])

    call_count = {"count": 0}

    def execute_side_effect():
        call_count["count"] += 1
        if call_count["count"] == 1:
            return flag_result
        else:
            return override_result

    mock_supabase_client.execute.side_effect = execute_side_effect

    result = await flag_service.get_flag_details("test_flag")

    assert result is not None
    assert result.name == "test_flag"
    assert result.enabled is True
    assert result.is_override is True
    assert result.description == "Test flag description"


@pytest.mark.asyncio
async def test_get_flag_details_not_found(flag_service, mock_supabase_client) -> None:
    """Test get_flag_details returns None for nonexistent flag."""
    mock_supabase_client.execute.return_value = Mock(data=[])

    result = await flag_service.get_flag_details("nonexistent_flag")

    assert result is None


@pytest.mark.asyncio
async def test_invalidate_cache(flag_service) -> None:
    """Test that invalidate_cache clears the cache."""
    cache_key = (flag_service.tenant_id, "test_flag")
    _shared_cache[cache_key] = True

    flag_service.invalidate_cache()

    # After invalidation, the cache should not contain any entries for this tenant
    tenant_keys = [key for key in _shared_cache.keys() if key[0] == flag_service.tenant_id]
    assert len(tenant_keys) == 0


@pytest.mark.asyncio
async def test_error_handling_returns_false(flag_service, mock_supabase_client) -> None:
    """Test that errors in is_enabled return False (fail closed)."""
    mock_supabase_client.execute.side_effect = Exception("Database error")

    result = await flag_service.is_enabled("test_flag")

    assert result is False


@pytest.mark.asyncio
async def test_error_handling_returns_empty_dict(flag_service, mock_supabase_client) -> None:
    """Test that errors in get_all_flags return empty dict."""
    mock_supabase_client.execute.side_effect = Exception("Database error")

    result = await flag_service.get_all_flags()

    assert result == {}
