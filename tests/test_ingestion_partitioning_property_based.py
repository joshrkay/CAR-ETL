"""Property-based tests for ingestion topic partitioning."""
import pytest
from hypothesis import given, strategies as st, assume
from src.ingestion.partitioning import get_partition_for_tenant, get_partition_key


@given(
    tenant_id=st.text(min_size=1, max_size=100),
    num_partitions=st.integers(min_value=1, max_value=1000)
)
def test_partition_always_in_range(tenant_id: str, num_partitions: int):
    """Property: Partition number is always in valid range [0, num_partitions)."""
    partition = get_partition_for_tenant(tenant_id, num_partitions)
    
    assert 0 <= partition < num_partitions, (
        f"Partition {partition} out of range [0, {num_partitions})"
    )


@given(
    tenant_id=st.text(min_size=1, max_size=100),
    num_partitions=st.integers(min_value=1, max_value=1000)
)
def test_partition_is_deterministic(tenant_id: str, num_partitions: int):
    """Property: Same tenant_id always produces same partition."""
    partition1 = get_partition_for_tenant(tenant_id, num_partitions)
    partition2 = get_partition_for_tenant(tenant_id, num_partitions)
    partition3 = get_partition_for_tenant(tenant_id, num_partitions)
    
    assert partition1 == partition2 == partition3, (
        f"Partition not consistent: {partition1}, {partition2}, {partition3}"
    )


@given(
    tenant_id=st.text(min_size=1, max_size=100),
    num_partitions1=st.integers(min_value=1, max_value=1000),
    num_partitions2=st.integers(min_value=1, max_value=1000)
)
def test_partition_depends_on_partition_count(
    tenant_id: str,
    num_partitions1: int,
    num_partitions2: int
):
    """Property: Same tenant may map to different partitions with different partition counts."""
    assume(num_partitions1 != num_partitions2)
    
    partition1 = get_partition_for_tenant(tenant_id, num_partitions1)
    partition2 = get_partition_for_tenant(tenant_id, num_partitions2)
    
    # Partitions must be valid for their respective partition counts
    assert 0 <= partition1 < num_partitions1
    assert 0 <= partition2 < num_partitions2


@given(tenant_id=st.text(min_size=1, max_size=100))
def test_partition_key_is_bytes(tenant_id: str):
    """Property: Partition key is always bytes."""
    key = get_partition_key(tenant_id)
    
    assert isinstance(key, bytes), f"Partition key is not bytes: {type(key)}"


@given(tenant_id=st.text(min_size=1, max_size=100))
def test_partition_key_is_idempotent(tenant_id: str):
    """Property: Same tenant_id always produces same partition key."""
    key1 = get_partition_key(tenant_id)
    key2 = get_partition_key(tenant_id)
    key3 = get_partition_key(tenant_id)
    
    assert key1 == key2 == key3, (
        f"Partition key not consistent: {key1!r}, {key2!r}, {key3!r}"
    )


@given(tenant_id=st.text(min_size=1, max_size=100))
def test_partition_key_roundtrip(tenant_id: str):
    """Property: Partition key can be decoded back to tenant_id."""
    key = get_partition_key(tenant_id)
    decoded = key.decode('utf-8')
    
    assert decoded == tenant_id, f"Roundtrip failed: {tenant_id!r} != {decoded!r}"


@given(
    tenant_id1=st.text(min_size=1, max_size=100),
    tenant_id2=st.text(min_size=1, max_size=100)
)
def test_different_tenants_different_keys(tenant_id1: str, tenant_id2: str):
    """Property: Different tenant IDs produce different partition keys."""
    assume(tenant_id1 != tenant_id2)
    
    key1 = get_partition_key(tenant_id1)
    key2 = get_partition_key(tenant_id2)
    
    assert key1 != key2, (
        f"Different tenants produced same key: {tenant_id1!r} and {tenant_id2!r}"
    )


@given(
    num_tenants=st.integers(min_value=10, max_value=100),
    num_partitions=st.integers(min_value=1, max_value=20)
)
def test_partition_distribution(num_tenants: int, num_partitions: int):
    """Property: Partitions are reasonably distributed across tenants."""
    # Generate unique tenant IDs
    tenant_ids = [f"tenant-{i:04d}" for i in range(num_tenants)]
    
    # Get partitions for all tenants
    partitions = [
        get_partition_for_tenant(tenant_id, num_partitions)
        for tenant_id in tenant_ids
    ]
    
    # Count partitions
    partition_counts = {}
    for partition in partitions:
        partition_counts[partition] = partition_counts.get(partition, 0) + 1
    
    # Check all partitions are used (for large enough tenant count)
    if num_tenants >= num_partitions * 2:
        # With enough tenants, expect all partitions to be used
        # (probabilistically very likely with good hash function)
        used_partitions = len(partition_counts)
        assert used_partitions >= num_partitions * 0.5, (
            f"Poor distribution: only {used_partitions}/{num_partitions} partitions used"
        )
    
    # Check no partition is massively overloaded
    # For small sample sizes, allow more variance
    max_count = max(partition_counts.values())
    expected_avg = num_tenants / num_partitions
    
    # Allow 5x variance for small samples, 3x for large samples
    # This accounts for statistical variance in hash distribution
    if num_tenants < 50:
        max_allowed = expected_avg * 5
    else:
        max_allowed = expected_avg * 3
    
    assert max_count <= max_allowed, (
        f"Partition overloaded: {max_count} tenants "
        f"(expected avg: {expected_avg:.2f}, max allowed: {max_allowed:.2f})"
    )


@given(
    tenant_id=st.one_of(
        st.text(alphabet=st.characters(min_codepoint=0, max_codepoint=1114111), min_size=1, max_size=100),
        st.binary(min_size=1, max_size=100).map(lambda b: b.decode('utf-8', errors='ignore')).filter(bool)
    ),
    num_partitions=st.integers(min_value=1, max_value=100)
)
def test_partition_handles_unicode(tenant_id: str, num_partitions: int):
    """Property: Partitioning handles all valid unicode strings."""
    try:
        partition = get_partition_for_tenant(tenant_id, num_partitions)
        assert 0 <= partition < num_partitions
    except Exception as e:
        pytest.fail(f"Failed to handle unicode tenant_id: {tenant_id!r}: {e}")


@given(
    tenant_id=st.text(min_size=1, max_size=100),
    num_partitions=st.integers(min_value=1, max_value=1000)
)
def test_partition_stability_across_runs(tenant_id: str, num_partitions: int):
    """Property: Partition assignment is stable across multiple runs."""
    # Get partition multiple times with some "noise" operations in between
    partitions = []
    for _ in range(10):
        partition = get_partition_for_tenant(tenant_id, num_partitions)
        partitions.append(partition)
        # Some noise operations
        _ = get_partition_key(tenant_id)
        _ = get_partition_for_tenant(f"noise-{tenant_id}", num_partitions)
    
    # All partitions should be identical
    assert len(set(partitions)) == 1, (
        f"Partition not stable across runs: {partitions}"
    )


@given(num_partitions=st.integers(max_value=0))
def test_partition_rejects_invalid_partition_count(num_partitions: int):
    """Property: Invalid partition counts are rejected."""
    with pytest.raises(ValueError, match="num_partitions must be greater than 0"):
        get_partition_for_tenant("tenant-123", num_partitions)
