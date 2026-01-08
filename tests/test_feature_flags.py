"""Unit tests for feature flag system."""
import pytest
from uuid import UUID, uuid4
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from src.features.service import FeatureFlagService


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
    return FeatureFlagService(mock_supabase_client, tenant_id)


@pytest.mark.asyncio
async def test_is_enabled_flag_exists_with_default(flag_service, mock_supabase_client):
    """Test is_enabled when flag exists with default value."""
    flag_id = uuid4()
    
    # Mock flag lookup
    mock_supabase_client.execute.return_value = Mock(
        data=[{"id": str(flag_id), "name": "test_flag", "enabled_default": True}]
    )
    
    # Mock tenant override lookup (no override)
    def execute_side_effect():
        call_count = getattr(execute_side_effect, "call_count", 0)
        execute_side_effect.call_count = call_count + 1
        
        if call_count == 1:
            # First call: flag lookup
            return Mock(data=[{"id": str(flag_id), "name": "test_flag", "enabled_default": True}])
        else:
            # Second call: tenant override lookup
            return Mock(data=[])
    
    mock_supabase_client.execute.side_effect = execute_side_effect
    
    result = await flag_service.is_enabled("test_flag")
    
    assert result is True
    assert "test_flag" in flag_service._cache


@pytest.mark.asyncio
async def test_is_enabled_flag_exists_with_override(flag_service, mock_supabase_client):
    """Test is_enabled when flag exists with tenant override."""
    flag_id = uuid4()
    tenant_id = flag_service.tenant_id
    
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
    assert "test_flag" in flag_service._cache


@pytest.mark.asyncio
async def test_is_enabled_flag_not_exists(flag_service, mock_supabase_client):
    """Test is_enabled when flag doesn't exist."""
    mock_supabase_client.execute.return_value = Mock(data=[])
    
    result = await flag_service.is_enabled("nonexistent_flag")
    
    assert result is False
    assert "nonexistent_flag" in flag_service._cache


@pytest.mark.asyncio
async def test_is_enabled_uses_cache(flag_service, mock_supabase_client):
    """Test that is_enabled uses cache when valid."""
    flag_id = uuid4()
    
    # Set up cache
    flag_service._cache["test_flag"] = True
    flag_service._cache_expires = datetime.utcnow() + timedelta(seconds=300)
    
    # Should not call execute if cache is valid
    result = await flag_service.is_enabled("test_flag")
    
    assert result is True
    # Verify execute was not called (cache was used)
    mock_supabase_client.execute.assert_not_called()


@pytest.mark.asyncio
async def test_is_enabled_cache_expired(flag_service, mock_supabase_client):
    """Test that is_enabled refreshes cache when expired."""
    flag_id = uuid4()
    
    # Set up expired cache
    flag_service._cache["test_flag"] = False
    flag_service._cache_expires = datetime.utcnow() - timedelta(seconds=1)
    
    # Mock fresh lookup
    mock_supabase_client.execute.return_value = Mock(
        data=[{"id": str(flag_id), "name": "test_flag", "enabled_default": True}]
    )
    
    def execute_side_effect():
        call_count = getattr(execute_side_effect, "call_count", 0)
        execute_side_effect.call_count = call_count + 1
        
        if call_count == 1:
            return Mock(data=[{"id": str(flag_id), "name": "test_flag", "enabled_default": True}])
        else:
            return Mock(data=[])
    
    mock_supabase_client.execute.side_effect = execute_side_effect
    
    result = await flag_service.is_enabled("test_flag")
    
    assert result is True  # Fresh lookup returns True
    assert flag_service._cache["test_flag"] is True  # Cache updated


@pytest.mark.asyncio
async def test_get_all_flags(flag_service, mock_supabase_client):
    """Test get_all_flags returns all flags with tenant overrides."""
    flag1_id = uuid4()
    flag2_id = uuid4()
    tenant_id = flag_service.tenant_id
    
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
    assert "flag1" in flag_service._cache
    assert "flag2" in flag_service._cache


@pytest.mark.asyncio
async def test_get_flag_details(flag_service, mock_supabase_client):
    """Test get_flag_details returns detailed flag information."""
    flag_id = uuid4()
    tenant_id = flag_service.tenant_id
    
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
async def test_get_flag_details_not_found(flag_service, mock_supabase_client):
    """Test get_flag_details returns None for nonexistent flag."""
    mock_supabase_client.execute.return_value = Mock(data=[])
    
    result = await flag_service.get_flag_details("nonexistent_flag")
    
    assert result is None


@pytest.mark.asyncio
async def test_invalidate_cache(flag_service):
    """Test that invalidate_cache clears the cache."""
    flag_service._cache["test_flag"] = True
    flag_service._cache_expires = datetime.utcnow() + timedelta(seconds=300)
    
    flag_service.invalidate_cache()
    
    assert len(flag_service._cache) == 0
    assert flag_service._cache_expires is None


@pytest.mark.asyncio
async def test_error_handling_returns_false(flag_service, mock_supabase_client):
    """Test that errors in is_enabled return False (fail closed)."""
    mock_supabase_client.execute.side_effect = Exception("Database error")
    
    result = await flag_service.is_enabled("test_flag")
    
    assert result is False


@pytest.mark.asyncio
async def test_error_handling_returns_empty_dict(flag_service, mock_supabase_client):
    """Test that errors in get_all_flags return empty dict."""
    mock_supabase_client.execute.side_effect = Exception("Database error")
    
    result = await flag_service.get_all_flags()
    
    assert result == {}
