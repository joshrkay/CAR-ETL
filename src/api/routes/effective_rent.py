"""
Effective Rent API Routes - Analytics Endpoints

Provides portfolio analytics for effective rent calculations.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from supabase import Client

from src.auth.models import AuthContext
from src.auth.decorators import require_permission
from src.dependencies import get_supabase_client
from src.services.effective_rent import EffectiveRentService
from src.db.models.effective_rent import (
    EffectiveRentListResponse,
    EffectiveRentSummary,
    TenantEffectiveRent,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["analytics", "rent"],
)


@router.get(
    "/effective-rent",
    response_model=EffectiveRentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all tenants by effective rent",
    description="""
    Calculate and list all tenants sorted by effective rent.

    Effective Rent = Base Rent + CAM + Tax + Insurance + Parking + Storage

    Security:
    - Requires authentication and 'documents:read' permission
    - Tenant isolation enforced via RLS
    - Only shows data for your tenant

    Returns tenants sorted by effective rent (highest first by default).
    """,
)
async def list_effective_rents(
    request: Request,
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limit number of results"),
    sort: str = Query("desc", regex="^(asc|desc)$", description="Sort order: 'asc' or 'desc'"),
    auth: AuthContext = Depends(require_permission("documents:read")),
    supabase: Client = Depends(get_supabase_client),
) -> EffectiveRentListResponse:
    """
    List all tenants with effective rent calculations.

    Args:
        request: FastAPI request object
        limit: Optional limit on number of results
        sort: Sort order ('asc' or 'desc')
        auth: Authenticated user context
        supabase: Supabase client with user JWT

    Returns:
        EffectiveRentListResponse with sorted tenant list

    Raises:
        HTTPException 401: User not authenticated
        HTTPException 403: Insufficient permissions
        HTTPException 500: Server error
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    user_id = str(auth.user_id)

    logger.info(
        "Listing effective rents",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "limit": limit,
            "sort": sort,
        },
    )

    try:
        service = EffectiveRentService(supabase)
        result = await service.calculate_all_effective_rents(
            limit=limit,
            sort_desc=(sort == "desc"),
        )

        logger.info(
            "Listed effective rents",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "tenant_count": result.total_count,
                "total_monthly": result.total_effective_monthly_rent,
            },
        )

        return result

    except Exception as e:
        logger.error(
            "Failed to list effective rents",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate effective rents",
        )


@router.get(
    "/effective-rent/highest",
    response_model=TenantEffectiveRent,
    status_code=status.HTTP_200_OK,
    summary="Get tenant with highest effective rent",
    description="""
    Get the tenant with the highest effective rent in your portfolio.

    Effective Rent = Base Rent + CAM + Tax + Insurance + Parking + Storage

    Security:
    - Requires authentication and 'documents:read' permission
    - Tenant isolation enforced via RLS

    Returns single tenant with highest total monthly obligations.
    """,
)
async def get_highest_effective_rent(
    request: Request,
    auth: AuthContext = Depends(require_permission("documents:read")),
    supabase: Client = Depends(get_supabase_client),
) -> TenantEffectiveRent:
    """
    Get tenant with highest effective rent.

    Args:
        request: FastAPI request object
        auth: Authenticated user context
        supabase: Supabase client with user JWT

    Returns:
        TenantEffectiveRent for highest rent tenant

    Raises:
        HTTPException 401: User not authenticated
        HTTPException 403: Insufficient permissions
        HTTPException 404: No rent data found
        HTTPException 500: Server error
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    user_id = str(auth.user_id)

    logger.info(
        "Getting highest effective rent",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
        },
    )

    try:
        service = EffectiveRentService(supabase)
        result = await service.get_highest_effective_rent()

        if not result:
            logger.info(
                "No rent data found",
                extra={
                    "request_id": request_id,
                    "tenant_id": tenant_id,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No rent data found for your tenant",
            )

        logger.info(
            "Retrieved highest effective rent",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "tenant_name": result.tenant_name,
                "effective_monthly": result.effective_monthly_rent,
            },
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get highest effective rent",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve highest effective rent",
        )


@router.get(
    "/effective-rent/summary",
    response_model=EffectiveRentSummary,
    status_code=status.HTTP_200_OK,
    summary="Get portfolio effective rent summary",
    description="""
    Get portfolio-level summary statistics for effective rent.

    Returns:
    - Total number of tenants
    - Highest effective rent tenant
    - Lowest effective rent tenant
    - Average effective monthly rent
    - Total portfolio monthly and annual rent

    Security:
    - Requires authentication and 'documents:read' permission
    - Tenant isolation enforced via RLS
    """,
)
async def get_effective_rent_summary(
    request: Request,
    auth: AuthContext = Depends(require_permission("documents:read")),
    supabase: Client = Depends(get_supabase_client),
) -> EffectiveRentSummary:
    """
    Get portfolio summary for effective rent.

    Args:
        request: FastAPI request object
        auth: Authenticated user context
        supabase: Supabase client with user JWT

    Returns:
        EffectiveRentSummary with portfolio metrics

    Raises:
        HTTPException 401: User not authenticated
        HTTPException 403: Insufficient permissions
        HTTPException 500: Server error
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    user_id = str(auth.user_id)

    logger.info(
        "Getting effective rent summary",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
        },
    )

    try:
        service = EffectiveRentService(supabase)
        summary = await service.get_summary()

        logger.info(
            "Retrieved effective rent summary",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "total_tenants": summary.total_tenants,
                "total_portfolio_monthly": summary.total_portfolio_monthly_rent,
            },
        )

        return summary

    except Exception as e:
        logger.error(
            "Failed to get effective rent summary",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve effective rent summary",
        )
