"""Pydantic models for audit events."""
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Audit event type categories."""

    # Authentication events
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"

    # Document events
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_VIEW = "document.view"
    DOCUMENT_DELETE = "document.delete"

    # Extraction events
    EXTRACTION_COMPLETE = "extraction.complete"
    EXTRACTION_OVERRIDE = "extraction.override"

    # Search events
    SEARCH_QUERY = "search.query"
    ASK_QUERY = "ask.query"

    # Export events
    EXPORT_GENERATE = "export.generate"
    EXPORT_DOWNLOAD = "export.download"

    # User management events
    USER_INVITE = "user.invite"
    USER_REMOVE = "user.remove"

    # API request events (from middleware)
    API_REQUEST = "api.request"


class ActionType(str, Enum):
    """CRUD action types."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"


class ResourceType(str, Enum):
    """Resource type categories."""
    DOCUMENT = "document"
    USER = "user"
    TENANT = "tenant"
    EXTRACTION = "extraction"
    SEARCH = "search"
    EXPORT = "export"
    API = "api"


class AuditEvent(BaseModel):
    """Audit event model for logging."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    user_id: UUID | None = Field(None, description="User UUID (null for system events)")
    event_type: str = Field(..., description="Event type (e.g., auth.login)")
    resource_type: str | None = Field(None, description="Resource type (e.g., document)")
    resource_id: str | None = Field(None, description="Resource identifier")
    action: str = Field(..., description="Action type (create, read, update, delete)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional event metadata")
    ip_address: str | None = Field(None, description="Client IP address")
    user_agent: str | None = Field(None, description="User agent string")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database insert."""
        return {
            "tenant_id": str(self.tenant_id),
            "user_id": str(self.user_id) if self.user_id else None,
            "event_type": self.event_type,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "metadata": self.metadata,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }
