"""
Connector Routes - Control Plane

Handles OAuth authentication and sync configuration for external data sources.
Enforces tenant isolation and encrypts sensitive credentials.
"""
import logging
from typing import Annotated, Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from pydantic import BaseModel, Field
from supabase import Client

from src.auth.models import AuthContext
from src.auth.decorators import require_permission
from src.dependencies import get_supabase_client
from src.connectors.sharepoint.oauth import SharePointOAuth, SharePointOAuthError
from src.connectors.sharepoint.client import SharePointClient, SharePointClientError
from src.connectors.sharepoint.sync import SharePointSync, SharePointSyncError
from src.connectors.sharepoint.state_store import OAuthStateStore
from src.utils.encryption import encrypt_value, decrypt_value
from src.dependencies import get_service_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/connectors/sharepoint",
    tags=["connectors", "sharepoint"],
)


# Request/Response Models

class OAuthStartResponse(BaseModel):
    """Response model for OAuth authorization URL."""
    authorization_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    """Request model for OAuth callback."""
    code: str = Field(..., description="Authorization code from OAuth provider")
    state: Optional[str] = Field(None, description="State parameter for CSRF protection")


class OAuthCallbackResponse(BaseModel):
    """Response model for OAuth callback."""
    connector_id: str
    status: str
    message: str


class SiteInfo(BaseModel):
    """SharePoint site information."""
    id: str
    name: str
    web_url: str
    display_name: Optional[str] = None
    description: Optional[str] = None


class DriveInfo(BaseModel):
    """SharePoint drive (document library) information."""
    id: str
    name: str
    web_url: str
    description: Optional[str] = None
    drive_type: Optional[str] = None


class SitesResponse(BaseModel):
    """Response model for list of SharePoint sites."""
    sites: List[SiteInfo]


class DrivesResponse(BaseModel):
    """Response model for list of SharePoint drives."""
    drives: List[DriveInfo]


class ConfigureRequest(BaseModel):
    """Request model for configuring connector sync target."""
    site_id: str = Field(..., description="SharePoint site ID")
    drive_id: str = Field(..., description="SharePoint drive (document library) ID")
    folder_path: str = Field(default="/", description="Folder path to sync (default: root)")


class ConfigureResponse(BaseModel):
    """Response model for connector configuration."""
    connector_id: str
    site_id: str
    drive_id: str
    folder_path: str
    status: str


class SyncResponse(BaseModel):
    """Response model for sync operation."""
    connector_id: str
    files_synced: int
    files_updated: int
    files_skipped: int
    errors: List[str]
    last_sync_at: Optional[str] = None


# Helper Functions

def _encrypt_connector_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encrypt sensitive fields in connector config.
    
    Args:
        config: Connector configuration dictionary
        
    Returns:
        Configuration with encrypted sensitive fields
    """
    encrypted = config.copy()
    
    if "access_token" in encrypted:
        encrypted["access_token"] = encrypt_value(encrypted["access_token"])
    
    if "refresh_token" in encrypted:
        encrypted["refresh_token"] = encrypt_value(encrypted["refresh_token"])
    
    return encrypted


def _decrypt_connector_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decrypt sensitive fields in connector config.
    
    Args:
        config: Connector configuration dictionary with encrypted fields
        
    Returns:
        Configuration with decrypted sensitive fields
        
    Raises:
        ValueError: If decryption fails
    """
    decrypted = config.copy()
    
    if "access_token" in decrypted:
        try:
            decrypted["access_token"] = decrypt_value(decrypted["access_token"])
        except ValueError:
            logger.error("Failed to decrypt access_token", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "DECRYPTION_ERROR", "message": "Failed to decrypt connector credentials"},
            )
    
    if "refresh_token" in decrypted:
        try:
            decrypted["refresh_token"] = decrypt_value(decrypted["refresh_token"])
        except ValueError:
            logger.error("Failed to decrypt refresh_token", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "DECRYPTION_ERROR", "message": "Failed to decrypt connector credentials"},
            )
    
    return decrypted


async def _get_or_create_connector(
    supabase: Client,
    tenant_id: UUID,
    connector_type: str,
) -> Dict[str, Any]:
    """
    Get existing connector or create new one for tenant.
    
    Args:
        supabase: Supabase client with user JWT
        tenant_id: Tenant identifier
        connector_type: Connector type ('sharepoint', 'google_drive')
        
    Returns:
        Connector record dictionary
    """
    result = (
        supabase.table("connectors")
        .select("*")
        .eq("tenant_id", str(tenant_id))
        .eq("type", connector_type)
        .maybe_single()
        .execute()
    )
    
    if result.data:
        return result.data
    
    connector_id = str(uuid4())
    connector_data = {
        "id": connector_id,
        "tenant_id": str(tenant_id),
        "type": connector_type,
        "config": {},
        "status": "active",
    }
    
    result = supabase.table("connectors").insert(connector_data).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "DATABASE_ERROR", "message": "Failed to create connector"},
        )
    
    return result.data[0]


# API Endpoints

@router.post(
    "/auth",
    response_model=OAuthStartResponse,
    status_code=status.HTTP_200_OK,
    summary="Start OAuth flow",
    description="Generate OAuth authorization URL for Microsoft Graph API authentication.",
)
async def start_oauth(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("connectors:write"))],
    supabase: Annotated[Client, Depends(get_supabase_client)],
) -> OAuthStartResponse:
    """
    Start OAuth2 flow for SharePoint authentication.
    
    Returns authorization URL that user should redirect to.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    
    logger.info(
        "OAuth flow initiated",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": str(auth.user_id),
        },
    )
    
    try:
        oauth = SharePointOAuth.from_env()
        state = str(uuid4())
        authorization_url = oauth.get_authorization_url(state=state)
        
        service_client = get_service_client()
        state_store = OAuthStateStore(service_client)
        await state_store.store_state(state=state, tenant_id=tenant_id)
        
        return OAuthStartResponse(
            authorization_url=authorization_url,
            state=state,
        )
    except ValueError as e:
        logger.error(
            "OAuth configuration error",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "OAUTH_CONFIG_ERROR",
                "message": "OAuth configuration is missing or invalid",
            },
        )


@router.get(
    "/callback",
    response_model=OAuthCallbackResponse,
    status_code=status.HTTP_200_OK,
    summary="OAuth callback",
    description="Handle OAuth callback and store encrypted tokens.",
)
async def oauth_callback(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("connectors:write"))],
    supabase: Annotated[Client, Depends(get_supabase_client)],
    code: str = Query(..., description="Authorization code"),
    state: Optional[str] = Query(None, description="State parameter"),
) -> OAuthCallbackResponse:
    """
    Handle OAuth callback and store encrypted tokens (authenticated version).
    """
    tenant_id = str(auth.tenant_id)
    return await _handle_oauth_callback(request, code, state, tenant_id, supabase)


async def _handle_oauth_callback(
    request: Request,
    code: str,
    state: Optional[str],
    tenant_id: str,
    supabase: Client,
) -> OAuthCallbackResponse:
    """Internal handler for OAuth callback."""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        "OAuth callback received",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
        },
    )
    
    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_STATE", "message": "State parameter is required"},
        )
    
    try:
        oauth = SharePointOAuth.from_env()
        token_data = await oauth.exchange_code_for_tokens(code=code, state=state)
        
        from uuid import UUID
        connector = await _get_or_create_connector(
            supabase=supabase,
            tenant_id=UUID(tenant_id),
            connector_type="sharepoint",
        )
        
        config = connector.get("config", {})
        config["access_token"] = token_data["access_token"]
        config["refresh_token"] = token_data.get("refresh_token", "")
        # Convert expires_in (seconds) to absolute timestamp
        expires_in = token_data.get("expires_in", 3600)
        config["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        
        encrypted_config = _encrypt_connector_config(config)
        
        result = (
            supabase.table("connectors")
            .update({"config": encrypted_config, "status": "active"})
            .eq("id", connector["id"])
            .execute()
        )
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "DATABASE_ERROR", "message": "Failed to update connector"},
            )
        
        logger.info(
            "OAuth tokens stored",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "connector_id": connector["id"],
            },
        )
        
        return OAuthCallbackResponse(
            connector_id=connector["id"],
            status="active",
            message="OAuth authentication successful",
        )
        
    except SharePointOAuthError as e:
        logger.error(
            "OAuth token exchange failed",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "OAUTH_ERROR", "message": str(e)},
        )
    except Exception:
        logger.error("Unexpected error in OAuth callback", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "OAuth callback failed"},
        )


async def oauth_callback_public(
    request: Request,
    code: str = Query(..., description="Authorization code"),
    state: Optional[str] = Query(None, description="State parameter"),
) -> OAuthCallbackResponse:
    """
    Handle OAuth callback from Microsoft (public endpoint).
    
    Validates state parameter to retrieve tenant_id, then processes callback.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_STATE", "message": "State parameter is required"},
        )
    
    service_client = get_service_client()
    state_store = OAuthStateStore(service_client)
    tenant_id = await state_store.get_tenant_id(state)
    
    if not tenant_id:
        logger.warning(
            "Invalid or expired OAuth state",
            extra={
                "request_id": request_id,
                "state": state[:8] + "..." if len(state) > 8 else state,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_STATE",
                "message": "Invalid or expired state parameter",
            },
        )
    
    return await _handle_oauth_callback(
        request=request,
        code=code,
        state=state,
        tenant_id=tenant_id,
        supabase=service_client,
    )


@router.post(
    "/sites",
    response_model=SitesResponse,
    status_code=status.HTTP_200_OK,
    summary="List SharePoint sites",
    description="List all SharePoint sites accessible to the authenticated user.",
)
async def list_sites(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("connectors:read"))],
    supabase: Annotated[Client, Depends(get_supabase_client)],
) -> SitesResponse:
    """
    List all SharePoint sites accessible to the user.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    
    connector = await _get_or_create_connector(
        supabase=supabase,
        tenant_id=auth.tenant_id,
        connector_type="sharepoint",
    )
    
    config = connector.get("config", {})
    if not config.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "NOT_AUTHENTICATED",
                "message": "SharePoint connector not authenticated. Complete OAuth flow first.",
            },
        )
    
    decrypted_config = _decrypt_connector_config(config)
    access_token = decrypted_config["access_token"]
    refresh_token = decrypted_config.get("refresh_token")
    
    try:
        oauth = SharePointOAuth.from_env()
        client = SharePointClient(
            access_token=access_token,
            refresh_token=refresh_token,
            oauth_handler=oauth,
        )
        
        sites_data = await client.list_sites()
        sites = [
            SiteInfo(
                id=site.get("id", ""),
                name=site.get("name", ""),
                web_url=site.get("webUrl", ""),
                display_name=site.get("displayName"),
                description=site.get("description"),
            )
            for site in sites_data
        ]
        
        return SitesResponse(sites=sites)
        
    except SharePointClientError as e:
        logger.error(
            "Failed to list SharePoint sites",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "SHAREPOINT_ERROR", "message": str(e)},
        )


@router.post(
    "/drives",
    response_model=DrivesResponse,
    status_code=status.HTTP_200_OK,
    summary="List SharePoint drives",
    description="List document libraries (drives) for a SharePoint site.",
)
async def list_drives(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("connectors:read"))],
    supabase: Annotated[Client, Depends(get_supabase_client)],
    site_id: str = Query(..., description="SharePoint site ID"),
) -> DrivesResponse:
    """
    List document libraries (drives) for a SharePoint site.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    
    connector = await _get_or_create_connector(
        supabase=supabase,
        tenant_id=auth.tenant_id,
        connector_type="sharepoint",
    )
    
    config = connector.get("config", {})
    if not config.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "NOT_AUTHENTICATED",
                "message": "SharePoint connector not authenticated. Complete OAuth flow first.",
            },
        )
    
    decrypted_config = _decrypt_connector_config(config)
    access_token = decrypted_config["access_token"]
    refresh_token = decrypted_config.get("refresh_token")
    
    try:
        oauth = SharePointOAuth.from_env()
        client = SharePointClient(
            access_token=access_token,
            refresh_token=refresh_token,
            oauth_handler=oauth,
        )
        
        drives_data = await client.list_drives(site_id=site_id)
        drives = [
            DriveInfo(
                id=drive.get("id", ""),
                name=drive.get("name", ""),
                web_url=drive.get("webUrl", ""),
                description=drive.get("description"),
                drive_type=drive.get("driveType"),
            )
            for drive in drives_data
        ]
        
        return DrivesResponse(drives=drives)
        
    except SharePointClientError as e:
        logger.error(
            "Failed to list SharePoint drives",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "site_id": site_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "SHAREPOINT_ERROR", "message": str(e)},
        )


@router.post(
    "/configure",
    response_model=ConfigureResponse,
    status_code=status.HTTP_200_OK,
    summary="Configure sync target",
    description="Set SharePoint site and drive for sync.",
)
async def configure_connector(
    request: Request,
    config_data: ConfigureRequest,
    auth: Annotated[AuthContext, Depends(require_permission("connectors:write"))],
    supabase: Annotated[Client, Depends(get_supabase_client)],
) -> ConfigureResponse:
    """
    Configure SharePoint connector sync target.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    
    connector = await _get_or_create_connector(
        supabase=supabase,
        tenant_id=auth.tenant_id,
        connector_type="sharepoint",
    )
    
    config = connector.get("config", {})
    config["site_id"] = config_data.site_id
    config["drive_id"] = config_data.drive_id
    config["folder_path"] = config_data.folder_path
    
    encrypted_config = _encrypt_connector_config(config)
    
    result = (
        supabase.table("connectors")
        .update({"config": encrypted_config})
        .eq("id", connector["id"])
        .execute()
    )
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "DATABASE_ERROR", "message": "Failed to update connector"},
        )
    
    logger.info(
        "Connector configured",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "connector_id": connector["id"],
            "site_id": config_data.site_id,
            "drive_id": config_data.drive_id,
        },
    )
    
    return ConfigureResponse(
        connector_id=connector["id"],
        site_id=config_data.site_id,
        drive_id=config_data.drive_id,
        folder_path=config_data.folder_path,
        status="active",
    )


@router.post(
    "/sync",
    response_model=SyncResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger sync",
    description="Perform delta sync of SharePoint files.",
)
async def trigger_sync(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_permission("connectors:write"))],
    supabase: Annotated[Client, Depends(get_supabase_client)],
) -> SyncResponse:
    """
    Trigger delta sync of SharePoint files.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    
    connector = await _get_or_create_connector(
        supabase=supabase,
        tenant_id=auth.tenant_id,
        connector_type="sharepoint",
    )
    
    config = connector.get("config", {})
    if not config.get("access_token") or not config.get("drive_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "NOT_CONFIGURED",
                "message": "Connector not configured. Complete OAuth and configure sync target first.",
            },
        )
    
    decrypted_config = _decrypt_connector_config(config)
    access_token = decrypted_config["access_token"]
    refresh_token = decrypted_config.get("refresh_token")
    drive_id = config.get("drive_id")
    folder_path = config.get("folder_path", "/")
    
    try:
        oauth = SharePointOAuth.from_env()
        client = SharePointClient(
            access_token=access_token,
            refresh_token=refresh_token,
            oauth_handler=oauth,
        )
        
        sync_handler = SharePointSync(
            supabase=supabase,
            tenant_id=auth.tenant_id,
            connector_id=UUID(connector["id"]),
        )
        
        stats = await sync_handler.sync_drive(
            client=client,
            drive_id=drive_id,
            folder_path=folder_path,
        )
        
        result = (
            supabase.table("connectors")
            .select("last_sync_at")
            .eq("id", connector["id"])
            .maybe_single()
            .execute()
        )
        
        last_sync_at = result.data.get("last_sync_at") if result.data else None
        
        logger.info(
            "Sync completed",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "connector_id": connector["id"],
                "files_synced": stats["files_synced"],
                "files_updated": stats["files_updated"],
            },
        )
        
        return SyncResponse(
            connector_id=connector["id"],
            files_synced=stats["files_synced"],
            files_updated=stats["files_updated"],
            files_skipped=stats["files_skipped"],
            errors=stats["errors"],
            last_sync_at=last_sync_at,
        )
        
    except (SharePointClientError, SharePointSyncError) as e:
        logger.error(
            "Sync failed",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "connector_id": connector["id"],
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "SYNC_ERROR", "message": str(e)},
        )
