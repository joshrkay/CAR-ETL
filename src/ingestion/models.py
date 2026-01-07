"""Ingestion event models for CAR Platform."""
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import hashlib


class SourceType(str, Enum):
    """Source type enumeration for ingestion events."""
    
    UPLOAD = "UPLOAD"
    EMAIL = "EMAIL"
    CLOUD_SYNC = "CLOUD_SYNC"


class IngestionEvent(BaseModel):
    """Ingestion event model for document ingestion.
    
    This model represents a unified ingestion event that can come from
    multiple sources (direct upload, email forwarding, cloud storage sync).
    All ingestion paths converge on this event type.
    """
    
    # Required fields
    tenant_id: str = Field(..., description="Tenant identifier (UUID)", min_length=1)
    source_type: SourceType = Field(..., description="Source type: UPLOAD, EMAIL, or CLOUD_SYNC")
    file_hash: str = Field(..., description="SHA-256 hash of file content (content-addressable storage key)", min_length=64, max_length=64)
    s3_uri: str = Field(..., description="S3 URI where file is stored (content hash as key)", min_length=1)
    original_filename: str = Field(..., description="Original filename from source", min_length=1)
    mime_type: str = Field(..., description="MIME type of the file (e.g., application/pdf)", min_length=1)
    timestamp: datetime = Field(..., description="ISO 8601 timestamp when ingestion occurred")
    
    # Optional fields
    source_path: Optional[str] = Field(None, description="Source path (e.g., email folder, cloud storage path)")
    parent_id: Optional[str] = Field(None, description="Parent document ID (for email attachments)")
    permissions_blob: Optional[Dict[str, Any]] = Field(None, description="Source permissions captured for downstream access control")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata (JSONB)")
    
    @field_validator("file_hash")
    @classmethod
    def validate_file_hash(cls, v: str) -> str:
        """Validate file_hash is a valid SHA-256 hash (64 hex characters).
        
        Args:
            v: File hash string.
        
        Returns:
            Validated file hash.
        
        Raises:
            ValueError: If hash format is invalid.
        """
        if len(v) != 64:
            raise ValueError("file_hash must be exactly 64 characters (SHA-256)")
        
        # Check if all characters are hexadecimal
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("file_hash must be a valid hexadecimal string")
        
        return v.lower()  # Normalize to lowercase
    
    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, v: str) -> str:
        """Validate tenant_id is a valid UUID format.
        
        Args:
            v: Tenant ID string.
        
        Returns:
            Validated tenant ID.
        
        Raises:
            ValueError: If UUID format is invalid.
        """
        import uuid
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("tenant_id must be a valid UUID")
        return v
    
    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware.
        
        Args:
            v: Timestamp datetime.
        
        Returns:
            Timezone-aware datetime.
        """
        if v.tzinfo is None:
            # Assume UTC if no timezone provided
            return v.replace(tzinfo=timezone.utc)
        return v
    
    def to_avro_dict(self) -> Dict[str, Any]:
        """Convert to dictionary compatible with Avro schema.
        
        Returns:
            Dictionary with Avro-compatible types.
        """
        # Handle source_type (may be enum or string due to use_enum_values=True)
        source_type_value = self.source_type
        if isinstance(source_type_value, SourceType):
            source_type_value = source_type_value.value
        
        result = {
            "tenant_id": self.tenant_id,
            "source_type": source_type_value,
            "file_hash": self.file_hash,
            "s3_uri": self.s3_uri,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "timestamp": int(self.timestamp.timestamp() * 1000),  # Milliseconds since epoch
        }
        
        # Add optional fields if present
        if self.source_path is not None:
            result["source_path"] = self.source_path
        if self.parent_id is not None:
            result["parent_id"] = self.parent_id
        if self.permissions_blob is not None:
            result["permissions_blob"] = self.permissions_blob
        if self.metadata is not None:
            result["metadata"] = self.metadata
        
        return result
    
    @classmethod
    def from_avro_dict(cls, data: Dict[str, Any]) -> "IngestionEvent":
        """Create IngestionEvent from Avro dictionary.
        
        Args:
            data: Dictionary from Avro deserialization.
        
        Returns:
            IngestionEvent instance.
        """
        # Convert timestamp from milliseconds to datetime
        if "timestamp" in data and isinstance(data["timestamp"], int):
            from datetime import timezone
            data["timestamp"] = datetime.fromtimestamp(data["timestamp"] / 1000.0, tz=timezone.utc)
        
        # Convert source_type string to enum
        if "source_type" in data and isinstance(data["source_type"], str):
            data["source_type"] = SourceType(data["source_type"])
        
        return cls(**data)
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


def compute_file_hash(file_content: bytes) -> str:
    """Compute SHA-256 hash of file content.
    
    Args:
        file_content: File content as bytes.
    
    Returns:
        SHA-256 hash as hexadecimal string (64 characters).
    """
    return hashlib.sha256(file_content).hexdigest()
