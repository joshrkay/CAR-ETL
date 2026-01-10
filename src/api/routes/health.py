"""Health check endpoints."""
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from src.services.health_checker import HealthChecker

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_liveness() -> dict[str, str]:
    """
    Liveness check endpoint.

    Returns 200 OK if the service is running.
    This is a simple check that doesn't verify dependencies.
    """
    return {"status": "healthy"}


@router.get("/health/ready", response_model=None)
async def health_readiness() -> JSONResponse | dict[str, Any]:
    """
    Readiness check endpoint.

    Performs comprehensive health checks on all system components:
    - Database connectivity
    - Storage service
    - Auth service

    Returns:
        - 200 OK if all services are healthy
        - 503 Service Unavailable if any critical service is down

    Response format:
    {
        "status": "healthy" | "unhealthy",
        "checks": {
            "database": {"status": "up", "latency_ms": 5},
            "storage": {"status": "up", "latency_ms": 12},
            "auth": {"status": "up", "latency_ms": 8}
        },
        "version": "1.0.0"
    }
    """
    checker = HealthChecker()
    checks = await checker.check_all()

    # Convert HealthCheckResult objects to dictionaries
    checks_dict: dict[str, dict[str, Any]] = {
        component: result.to_dict()
        for component, result in checks.items()
    }

    # Determine overall status
    overall_status = checker.get_overall_status(checks)

    # Prepare response
    response_data = {
        "status": overall_status,
        "checks": checks_dict,
        "version": "1.0.0",
    }

    # Return 503 if unhealthy, 200 otherwise
    if overall_status == "unhealthy":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response_data,
        )

    return response_data
