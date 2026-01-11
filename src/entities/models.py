"""Entity domain models."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

JsonValue = Union[
    str,
    int,
    float,
    bool,
    None,
    List["JsonValue"],
    Dict[str, "JsonValue"],
]


class EntityType(str, Enum):
    """Supported entity types."""

    PORTFOLIO = "portfolio"
    ASSET = "asset"
    TENANT = "tenant"
    LANDLORD = "landlord"
    LEASE = "lease"


class EntityStatus(str, Enum):
    """Entity lifecycle status."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class Entity(BaseModel):
    """Entity model for polymorphic entity records."""

    id: UUID = Field(..., description="Entity UUID")
    tenant_id: UUID = Field(..., description="Tenant UUID")
    entity_type: EntityType = Field(..., description="Entity type")
    name: str = Field(..., min_length=1, description="Entity name")
    canonical_name: str = Field(..., min_length=1, description="Normalized entity name")
    external_id: Optional[str] = Field(None, description="Customer external identifier")
    parent_id: Optional[UUID] = Field(None, description="Parent entity UUID")
    attributes: Dict[str, JsonValue] = Field(
        default_factory=dict, description="Entity attributes as JSON"
    )
    source_document_id: Optional[UUID] = Field(
        None, description="Source document UUID"
    )
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Confidence score"
    )
    status: EntityStatus = Field(default=EntityStatus.ACTIVE, description="Entity status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class EntityRelationship(BaseModel):
    """Entity relationship model."""

    id: UUID = Field(..., description="Relationship UUID")
    tenant_id: UUID = Field(..., description="Tenant UUID")
    from_entity_id: UUID = Field(..., description="Source entity UUID")
    to_entity_id: UUID = Field(..., description="Target entity UUID")
    relationship_type: str = Field(..., min_length=1, description="Relationship type")
    attributes: Dict[str, JsonValue] = Field(
        default_factory=dict, description="Relationship attributes as JSON"
    )
    start_date: Optional[date] = Field(None, description="Relationship start date")
    end_date: Optional[date] = Field(None, description="Relationship end date")
    source_document_id: Optional[UUID] = Field(
        None, description="Source document UUID"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
