"""
Effective Rent API Routes - Analytics Endpoints

Provides portfolio analytics for effective rent calculations.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from src.auth.decorators import require_permission
from src.auth.models import AuthContext
from src.db.models.effective_rent import (
    EffectiveRentListResponse,
    EffectiveRentSummary,
    PortfolioMetrics,
    RentByPropertyResponse,
    RentConcentrationResponse,
    RentPerSFResponse,
    TenantEffectiveRent,
)
from src.dependencies import get_supabase_client
from src.services.effective_rent import EffectiveRentService
from supabase import Client

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
    limit: int | None = Query(None, ge=1, le=1000, description="Limit number of results"),
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


@router.get(
    "/rent-by-property",
    response_model=RentByPropertyResponse,
    status_code=status.HTTP_200_OK,
    summary="Get rent grouped by property",
    description="""
    Calculate rent totals grouped by property/building.

    Returns list of properties with:
    - Total monthly and annual rent per property
    - Tenant count per property
    - Average rent per tenant
    - List of all tenants in each property

    Properties sorted by total rent (highest first).

    Security:
    - Requires authentication and 'documents:read' permission
    - Tenant isolation enforced via RLS
    """,
)
async def get_rent_by_property(
    request: Request,
    auth: AuthContext = Depends(require_permission("documents:read")),
    supabase: Client = Depends(get_supabase_client),
) -> RentByPropertyResponse:
    """
    Get rent grouped by property.

    Args:
        request: FastAPI request object
        auth: Authenticated user context
        supabase: Supabase client with user JWT

    Returns:
        RentByPropertyResponse with property-level summaries

    Raises:
        HTTPException 401: User not authenticated
        HTTPException 403: Insufficient permissions
        HTTPException 500: Server error
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    user_id = str(auth.user_id)

    logger.info(
        "Getting rent by property",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
        },
    )

    try:
        service = EffectiveRentService(supabase)
        result = await service.calculate_rent_by_property()

        logger.info(
            "Retrieved rent by property",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "property_count": result.total_properties,
            },
        )

        return result

    except Exception as e:
        logger.error(
            "Failed to get rent by property",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate rent by property",
        )


@router.get(
    "/rent-concentration",
    response_model=RentConcentrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get rent concentration analysis",
    description="""
    Analyze rent concentration - which tenants contribute most to portfolio rent.

    Returns top tenants with:
    - Percentage of total portfolio rent
    - Cumulative percentage
    - Effective rent amounts

    Useful for identifying concentration risk (e.g., if top 3 tenants = 50% of rent).

    Security:
    - Requires authentication and 'documents:read' permission
    - Tenant isolation enforced via RLS
    """,
)
async def get_rent_concentration(
    request: Request,
    top_n: int = Query(20, ge=1, le=100, description="Number of top tenants to return"),
    auth: AuthContext = Depends(require_permission("documents:read")),
    supabase: Client = Depends(get_supabase_client),
) -> RentConcentrationResponse:
    """
    Get rent concentration analysis.

    Args:
        request: FastAPI request object
        top_n: Number of top tenants to analyze
        auth: Authenticated user context
        supabase: Supabase client with user JWT

    Returns:
        RentConcentrationResponse with concentration metrics

    Raises:
        HTTPException 401: User not authenticated
        HTTPException 403: Insufficient permissions
        HTTPException 500: Server error
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    user_id = str(auth.user_id)

    logger.info(
        "Getting rent concentration",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "top_n": top_n,
        },
    )

    try:
        service = EffectiveRentService(supabase)
        result = await service.calculate_rent_concentration(top_n=top_n)

        logger.info(
            "Retrieved rent concentration",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "top_10_concentration": result.top_10_concentration,
            },
        )

        return result

    except Exception as e:
        logger.error(
            "Failed to get rent concentration",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate rent concentration",
        )


@router.get(
    "/rent-per-sf",
    response_model=RentPerSFResponse,
    status_code=status.HTTP_200_OK,
    summary="Get rent per square foot analysis",
    description="""
    Analyze rent efficiency using rent per square foot metrics.

    Returns tenants with SF data showing:
    - Monthly and annual rent per SF
    - Total square footage
    - Portfolio average rent per SF

    Useful for comparing tenant rates and identifying below/above-market rents.

    Security:
    - Requires authentication and 'documents:read' permission
    - Tenant isolation enforced via RLS
    """,
)
async def get_rent_per_sf(
    request: Request,
    auth: AuthContext = Depends(require_permission("documents:read")),
    supabase: Client = Depends(get_supabase_client),
) -> RentPerSFResponse:
    """
    Get rent per square foot analysis.

    Args:
        request: FastAPI request object
        auth: Authenticated user context
        supabase: Supabase client with user JWT

    Returns:
        RentPerSFResponse with rent per SF metrics

    Raises:
        HTTPException 401: User not authenticated
        HTTPException 403: Insufficient permissions
        HTTPException 500: Server error
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    user_id = str(auth.user_id)

    logger.info(
        "Getting rent per SF",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
        },
    )

    try:
        service = EffectiveRentService(supabase)
        result = await service.calculate_rent_per_sf()

        logger.info(
            "Retrieved rent per SF",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "tenant_count": len(result.tenants),
                "avg_annual_per_sf": result.average_rent_per_sf_annual,
            },
        )

        return result

    except Exception as e:
        logger.error(
            "Failed to get rent per SF",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate rent per SF",
        )


@router.get(
    "/portfolio-metrics",
    response_model=PortfolioMetrics,
    status_code=status.HTTP_200_OK,
    summary="Get comprehensive portfolio health metrics",
    description="""
    Get comprehensive dashboard metrics for portfolio health.

    Returns:
    - Tenant and property counts
    - Total and average rent metrics
    - Space utilization metrics
    - Concentration risk analysis (top 1, 5, 10 tenants)
    - Average extraction confidence

    Perfect for executive dashboards and portfolio overview.

    Security:
    - Requires authentication and 'documents:read' permission
    - Tenant isolation enforced via RLS
    """,
)
async def get_portfolio_metrics(
    request: Request,
    auth: AuthContext = Depends(require_permission("documents:read")),
    supabase: Client = Depends(get_supabase_client),
) -> PortfolioMetrics:
    """
    Get comprehensive portfolio metrics.

    Args:
        request: FastAPI request object
        auth: Authenticated user context
        supabase: Supabase client with user JWT

    Returns:
        PortfolioMetrics with comprehensive analytics

    Raises:
        HTTPException 401: User not authenticated
        HTTPException 403: Insufficient permissions
        HTTPException 500: Server error
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    user_id = str(auth.user_id)

    logger.info(
        "Getting portfolio metrics",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
        },
    )

    try:
        service = EffectiveRentService(supabase)
        metrics = await service.calculate_portfolio_metrics()

        logger.info(
            "Retrieved portfolio metrics",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "total_tenants": metrics.total_tenants,
                "total_properties": metrics.total_properties,
                "total_monthly": metrics.total_monthly_rent,
            },
        )

        return metrics

    except Exception as e:
        logger.error(
            "Failed to get portfolio metrics",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate portfolio metrics",
        )
