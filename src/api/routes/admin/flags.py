"""Admin endpoints for feature flag management."""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated, List
from uuid import UUID
from supabase import Client

from src.auth.models import AuthContext
from src.dependencies import get_current_user, require_role, get_supabase_client
from src.features.models import (
    FeatureFlag,
    FeatureFlagCreate,
    TenantFeatureFlagUpdate,
    FeatureFlagResponse,
)
from src.features.service import FeatureFlagService

router = APIRouter(prefix="/api/v1/admin/flags", tags=["admin", "feature-flags"])


@router.get("", response_model=List[FeatureFlag])
async def list_all_flags(
    supabase: Annotated[Client, Depends(get_supabase_client)],
    auth: Annotated[AuthContext, Depends(require_role("Admin"))],
):
    """
    List all feature flags (admin only).
    
    Requires Admin role.
    """
    try:
        result = (
            supabase.table("feature_flags")
            .select("*")
            .order("name")
            .execute()
        )
        
        return [
            FeatureFlag(**flag) for flag in (result.data or [])
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "FETCH_ERROR",
                "message": f"Failed to fetch feature flags: {str(e)}",
            },
        )


@router.post("", response_model=FeatureFlag, status_code=status.HTTP_201_CREATED)
async def create_flag(
    flag_data: FeatureFlagCreate,
    supabase: Annotated[Client, Depends(get_supabase_client)],
    auth: Annotated[AuthContext, Depends(require_role("Admin"))],
):
    """
    Create a new feature flag (admin only).
    
    Requires Admin role.
    """
    try:
        # Check if flag with this name already exists
        existing = (
            supabase.table("feature_flags")
            .select("id")
            .eq("name", flag_data.name)
            .limit(1)
            .execute()
        )
        
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "FLAG_EXISTS",
                    "message": f"Feature flag '{flag_data.name}' already exists",
                },
            )
        
        # Create the flag
        result = (
            supabase.table("feature_flags")
            .insert({
                "name": flag_data.name,
                "description": flag_data.description,
                "enabled_default": flag_data.enabled_default,
            })
            .execute()
        )
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": "CREATE_ERROR",
                    "message": "Failed to create feature flag",
                },
            )
        
        return FeatureFlag(**result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "CREATE_ERROR",
                "message": f"Failed to create feature flag: {str(e)}",
            },
        )


@router.put("/{flag_name}/tenants/{tenant_id}", response_model=dict)
async def set_tenant_override(
    flag_name: str,
    tenant_id: UUID,
    override_data: TenantFeatureFlagUpdate,
    supabase: Annotated[Client, Depends(get_supabase_client)],
    auth: Annotated[AuthContext, Depends(require_role("Admin"))],
):
    """
    Set tenant-specific feature flag override (admin only).
    
    Requires Admin role.
    """
    try:
        # Get the flag ID
        flag_result = (
            supabase.table("feature_flags")
            .select("id")
            .eq("name", flag_name)
            .limit(1)
            .execute()
        )
        
        if not flag_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "FLAG_NOT_FOUND",
                    "message": f"Feature flag '{flag_name}' not found",
                },
            )
        
        flag_id = flag_result.data[0]["id"]
        
        # Check if override already exists
        existing = (
            supabase.table("tenant_feature_flags")
            .select("id")
            .eq("tenant_id", str(tenant_id))
            .eq("flag_id", str(flag_id))
            .limit(1)
            .execute()
        )
        
        if existing.data:
            # Update existing override
            result = (
                supabase.table("tenant_feature_flags")
                .update({"enabled": override_data.enabled})
                .eq("id", existing.data[0]["id"])
                .execute()
            )
        else:
            # Create new override
            result = (
                supabase.table("tenant_feature_flags")
                .insert({
                    "tenant_id": str(tenant_id),
                    "flag_id": str(flag_id),
                    "enabled": override_data.enabled,
                })
                .execute()
            )
        
        # Invalidate cache for this tenant (if service instance exists)
        # Note: In a real app, you might want to use a cache invalidation service
        
        return {
            "flag_name": flag_name,
            "tenant_id": str(tenant_id),
            "enabled": override_data.enabled,
            "message": "Tenant override updated successfully",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "UPDATE_ERROR",
                "message": f"Failed to update tenant override: {str(e)}",
            },
        )


@router.delete("/{flag_name}/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant_override(
    flag_name: str,
    tenant_id: UUID,
    supabase: Annotated[Client, Depends(get_supabase_client)],
    auth: Annotated[AuthContext, Depends(require_role("Admin"))],
):
    """
    Delete tenant-specific feature flag override (admin only).
    
    This will cause the tenant to fall back to the default flag value.
    Requires Admin role.
    """
    try:
        # Get the flag ID
        flag_result = (
            supabase.table("feature_flags")
            .select("id")
            .eq("name", flag_name)
            .limit(1)
            .execute()
        )
        
        if not flag_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "FLAG_NOT_FOUND",
                    "message": f"Feature flag '{flag_name}' not found",
                },
            )
        
        flag_id = flag_result.data[0]["id"]
        
        # Delete the override
        result = (
            supabase.table("tenant_feature_flags")
            .delete()
            .eq("tenant_id", str(tenant_id))
            .eq("flag_id", str(flag_id))
            .execute()
        )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "DELETE_ERROR",
                "message": f"Failed to delete tenant override: {str(e)}",
            },
        )


@router.get("/{flag_name}", response_model=FeatureFlagResponse)
async def get_flag_details(
    flag_name: str,
    flags: Annotated[FeatureFlagService, Depends(get_feature_flags)],
    auth: Annotated[AuthContext, Depends(get_current_user)],
):
    """
    Get details about a specific feature flag for the current tenant.
    
    Available to all authenticated users.
    """
    flag_details = await flags.get_flag_details(flag_name)
    
    if not flag_details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "FLAG_NOT_FOUND",
                "message": f"Feature flag '{flag_name}' not found",
            },
        )
    
    return flag_details
