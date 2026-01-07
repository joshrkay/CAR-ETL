"""Partitioning utilities for tenant-based message routing."""
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_partition_for_tenant(tenant_id: str, num_partitions: int) -> int:
    """Get partition number for a tenant_id.
    
    Uses consistent hashing to ensure all messages for a tenant
    go to the same partition, maintaining ordering guarantees.
    
    Args:
        tenant_id: Tenant identifier (UUID string).
        num_partitions: Total number of partitions.
    
    Returns:
        Partition number (0 to num_partitions - 1).
    
    Raises:
        ValueError: If num_partitions is <= 0.
    """
    if num_partitions <= 0:
        raise ValueError("num_partitions must be greater than 0")
    
    # Use MD5 hash of tenant_id for consistent partitioning
    # MD5 is sufficient for partitioning (not security-critical)
    hash_bytes = hashlib.md5(tenant_id.encode('utf-8')).digest()
    hash_int = int.from_bytes(hash_bytes, byteorder='big')
    
    partition = hash_int % num_partitions
    
    logger.debug(f"Tenant {tenant_id} -> partition {partition} (out of {num_partitions})")
    
    return partition


def get_partition_key(tenant_id: str) -> Optional[bytes]:
    """Get partition key for Kafka message.
    
    Using tenant_id as partition key ensures all messages for a tenant
    go to the same partition, maintaining ordering.
    
    Args:
        tenant_id: Tenant identifier (UUID string).
    
    Returns:
        Partition key as bytes (tenant_id encoded).
    """
    return tenant_id.encode('utf-8')
