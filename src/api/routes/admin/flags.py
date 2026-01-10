"""Admin endpoints for feature flag management."""
import logging
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.auth.models import AuthContext
from src.dependencies import get_feature_flags, get_supabase_client, require_role
from src.features.models import (
    FeatureFlag,
    FeatureFlagCreate,
    FeatureFlagResponse,
    TenantFeatureFlagUpdate,
)
from src.features.service import FeatureFlagService
from supabase import Client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/flags", tags=["admin", "feature-flags"])


@router.get("", response_model=list[FeatureFlag])
async def list_all_flags(
    supabase: Annotated[Client, Depends(get_supabase_client)],
    auth: Annotated[AuthContext, Depends(require_role("Admin"))],
) -> list[FeatureFlag]:
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

        flags_list: list[FeatureFlag] = []
        if result.data:
            for flag in result.data:
                flag_dict = cast(dict[str, Any], flag)
                flags_list.append(FeatureFlag(**flag_dict))
        return flags_list
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
) -> FeatureFlag:
    """
    Create a new feature flag (admin only).

    Requires Admin role. Non-admins cannot modify flags.
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

        flag_dict = cast(dict[str, Any], result.data[0])
        return FeatureFlag(**flag_dict)

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
) -> dict[str, Any]:
    """
    Set tenant-specific feature flag override (admin only).

    Requires Admin role. Non-admins cannot modify flags.
    Enforces tenant isolation - admins can only modify flags for their own tenant.
    """
    # CRITICAL: Enforce tenant isolation - admins can only modify their own tenant's flags
    # Convert to string for robust comparison (handles UUID objects and string representations)
    if str(tenant_id) != str(auth.tenant_id):
        logger.warning(
            "Cross-tenant access attempt blocked",
            extra={
                "event_type": "CROSS_TENANT_ACCESS_DENIED",
                "user_id": str(auth.user_id),
                "user_tenant_id": str(auth.tenant_id),
                "requested_tenant_id": str(tenant_id),
                "flag_name": flag_name,
                "endpoint": "set_tenant_override",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CROSS_TENANT_ACCESS_DENIED",
                "message": "Tenant isolation is absolute. Admins can only modify feature flags for their own tenant.",
            },
        )

    # After validation, use auth.tenant_id (not URL parameter) for all operations
    # This ensures we never accidentally use an unvalidated tenant_id
    validated_tenant_id = auth.tenant_id

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

        flag_dict = cast(dict[str, Any], flag_result.data[0])
        flag_id = str(flag_dict.get("id", ""))

        # Check if override already exists
        existing = (
            supabase.table("tenant_feature_flags")
            .select("id")
            .eq("tenant_id", str(validated_tenant_id))
            .eq("flag_id", flag_id)
            .limit(1)
            .execute()
        )

        if existing.data:
            # Update existing override
            existing_dict = cast(dict[str, Any], existing.data[0])
            existing_id = str(existing_dict.get("id", ""))
            (
                supabase.table("tenant_feature_flags")
                .update({"enabled": override_data.enabled})
                .eq("id", existing_id)
                .execute()
            )
        else:
            # Create new override
            (
                supabase.table("tenant_feature_flags")
                .insert({
                    "tenant_id": str(validated_tenant_id),
                    "flag_id": str(flag_id),
                    "enabled": override_data.enabled,
                })
                .execute()
            )

        # Invalidate shared cache for this tenant and flag
        flag_service = FeatureFlagService(supabase, validated_tenant_id)
        flag_service.invalidate_cache(flag_name)

        return {
            "flag_name": flag_name,
            "tenant_id": str(validated_tenant_id),
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
) -> None:
    """
    Delete tenant-specific feature flag override (admin only).

    This will cause the tenant to fall back to the default flag value.
    Requires Admin role. Non-admins cannot modify flags.
    Enforces tenant isolation - admins can only delete flags for their own tenant.
    """
    # CRITICAL: Enforce tenant isolation - admins can only modify their own tenant's flags
    # Convert to string for robust comparison (handles UUID objects and string representations)
    if str(tenant_id) != str(auth.tenant_id):
        logger.warning(
            "Cross-tenant access attempt blocked",
            extra={
                "event_type": "CROSS_TENANT_ACCESS_DENIED",
                "user_id": str(auth.user_id),
                "user_tenant_id": str(auth.tenant_id),
                "requested_tenant_id": str(tenant_id),
                "flag_name": flag_name,
                "endpoint": "delete_tenant_override",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CROSS_TENANT_ACCESS_DENIED",
                "message": "Tenant isolation is absolute. Admins can only modify feature flags for their own tenant.",
            },
        )

    # After validation, use auth.tenant_id (not URL parameter) for all operations
    # This ensures we never accidentally use an unvalidated tenant_id
    validated_tenant_id = auth.tenant_id

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

        flag_dict = cast(dict[str, Any], flag_result.data[0])
        flag_id = str(flag_dict.get("id", ""))

        # Delete the override
        (
            supabase.table("tenant_feature_flags")
            .delete()
            .eq("tenant_id", str(validated_tenant_id))
            .eq("flag_id", str(flag_id))
            .execute()
        )

        # Invalidate shared cache for this tenant and flag
        flag_service = FeatureFlagService(supabase, validated_tenant_id)
        flag_service.invalidate_cache(flag_name)

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
) -> FeatureFlagResponse:
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
