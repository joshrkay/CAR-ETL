"""Audit log entry models for immutable audit trail."""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    """Immutable audit log entry model.
    
    All fields are required for compliance and non-repudiation.
    """
    
    user_id: str = Field(..., description="User ID who performed the action")
    tenant_id: str = Field(..., description="Tenant ID where action occurred")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the action")
    action_type: str = Field(..., description="Type of action performed")
    resource_id: Optional[str] = Field(None, description="ID of the resource affected")
    request_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional request metadata (method, path, IP, etc.)"
    )
    
    class Config:
        """Pydantic configuration."""
        frozen = True  # Make model immutable after creation
        json_schema_extra = {
            "example": {
                "user_id": "auth0|123",
                "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2024-01-15T10:30:00Z",
                "action_type": "document.upload",
                "resource_id": "doc-456",
                "request_metadata": {
                    "method": "POST",
                    "path": "/api/v1/documents",
                    "ip_address": "192.168.1.1",
                    "user_agent": "Mozilla/5.0"
                }
            }
        }
    
    def to_json(self) -> str:
        """Convert audit entry to JSON string.
        
        Returns:
            JSON string representation of the audit entry.
        """
        return self.model_dump_json(indent=None, exclude_none=False)
    
    @classmethod
    def create(
        cls,
        user_id: str,
        tenant_id: str,
        action_type: str,
        resource_id: Optional[str] = None,
        request_metadata: Optional[Dict[str, Any]] = None
    ) -> "AuditLogEntry":
        """Create a new audit log entry with current timestamp.
        
        Args:
            user_id: User ID who performed the action.
            tenant_id: Tenant ID where action occurred.
            action_type: Type of action performed.
            resource_id: Optional ID of the resource affected.
            request_metadata: Optional additional request metadata.
        
        Returns:
            New AuditLogEntry instance with current timestamp.
        """
        return cls(
            user_id=user_id,
            tenant_id=tenant_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            action_type=action_type,
            resource_id=resource_id,
            request_metadata=request_metadata or {}
        )
