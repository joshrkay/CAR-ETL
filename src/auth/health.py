"""Health check endpoint for Auth0 connectivity verification."""
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from .auth0_client import Auth0ManagementClient, Auth0TokenError, Auth0APIError
from .config import get_auth0_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    auth0_connected: bool
    auth0_domain: str
    message: Optional[str] = None


class HealthDetail(BaseModel):
    """Detailed health check response."""

    status: str
    auth0: Dict[str, Any]
    timestamp: str


def check_auth0_health() -> Dict[str, Any]:
    """Check Auth0 connectivity and return detailed status."""
    config = get_auth0_config()
    client = Auth0ManagementClient(config)

    health_info: Dict[str, Any] = {
        "domain": config.domain,
        "api_identifier": config.api_identifier,
        "connected": False,
        "error": None
    }

    try:
        is_connected = client.verify_connectivity()
        health_info["connected"] = is_connected
        if is_connected:
            health_info["management_api_url"] = config.management_api_url
    except Auth0TokenError as e:
        health_info["error"] = f"Token acquisition failed: {str(e)}"
        logger.error("Auth0 token error during health check", extra={"error": str(e)})
    except Auth0APIError as e:
        health_info["error"] = f"API error: {str(e)}"
        logger.error("Auth0 API error during health check", extra={"error": str(e)})
    except Exception as e:
        health_info["error"] = f"Unexpected error: {str(e)}"
        logger.exception("Unexpected error during Auth0 health check")

    return health_info


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check endpoint."""
    config = get_auth0_config()
    auth0_info = check_auth0_health()

    if auth0_info["connected"]:
        return HealthResponse(
            status="healthy",
            auth0_connected=True,
            auth0_domain=config.domain,
            message="Auth0 connectivity verified"
        )

    return HealthResponse(
        status="degraded",
        auth0_connected=False,
        auth0_domain=config.domain,
        message=auth0_info.get("error", "Auth0 connectivity check failed")
    )


@router.get("/detailed", response_model=HealthDetail)
async def detailed_health_check() -> HealthDetail:
    """Detailed health check endpoint with Auth0 status."""
    from datetime import datetime

    auth0_info = check_auth0_health()

    if not auth0_info["connected"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "auth0": auth0_info,
                "message": "Auth0 connectivity check failed"
            }
        )

    return HealthDetail(
        status="healthy",
        auth0=auth0_info,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
