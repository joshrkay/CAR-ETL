"""Pydantic models for feature flags."""
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class FeatureFlag(BaseModel):
    """Feature flag definition."""
    
    id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    enabled_default: bool = False
    created_at: datetime
    updated_at: datetime


class TenantFeatureFlag(BaseModel):
    """Tenant-specific feature flag override."""
    
    id: UUID
    tenant_id: UUID
    flag_id: UUID
    enabled: bool
    created_at: datetime
    updated_at: datetime


class FeatureFlagCreate(BaseModel):
    """Request model for creating a feature flag."""
    
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    enabled_default: bool = False


class TenantFeatureFlagUpdate(BaseModel):
    """Request model for updating tenant feature flag."""
    
    enabled: bool


class FeatureFlagResponse(BaseModel):
    """Response model for feature flag with tenant override."""
    
    name: str
    enabled: bool
    is_override: bool = Field(..., description="Whether this is a tenant override or default")
    description: Optional[str] = None
