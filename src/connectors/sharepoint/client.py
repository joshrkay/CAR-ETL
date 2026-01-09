"""Microsoft Graph API client for SharePoint operations."""
import logging
from typing import List, Dict, Any, Optional
import httpx
from src.connectors.sharepoint.oauth import SharePointOAuth, SharePointOAuthError

logger = logging.getLogger(__name__)


class SharePointClientError(Exception):
    """Error for SharePoint API operations."""
    pass


class SharePointClient:
    """Client for Microsoft Graph API SharePoint operations."""
    
    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
    
    def __init__(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        oauth_handler: Optional[SharePointOAuth] = None,
    ):
        """
        Initialize SharePoint Graph API client.
        
        Args:
            access_token: OAuth access token
            refresh_token: Optional refresh token for token renewal
            oauth_handler: Optional OAuth handler for token refresh
        """
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.oauth_handler = oauth_handler
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retry_on_auth_error: bool = True,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Graph API with automatic token refresh.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (relative to GRAPH_API_BASE)
            params: Query parameters
            json_data: JSON request body
            retry_on_auth_error: Whether to retry with refreshed token on 401
            
        Returns:
            JSON response data
            
        Raises:
            SharePointClientError: If request fails
        """
        url = f"{self.GRAPH_API_BASE}/{endpoint.lstrip('/')}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self._headers,
                    params=params,
                    json=json_data,
                    timeout=30.0,
                )
                
                if response.status_code == 401 and retry_on_auth_error:
                    if self.oauth_handler and self.refresh_token:
                        logger.info("Access token expired, refreshing...")
                        token_data = await self.oauth_handler.refresh_access_token(
                            self.refresh_token
                        )
                        self.access_token = token_data["access_token"]
                        if "refresh_token" in token_data:
                            self.refresh_token = token_data["refresh_token"]
                        self._headers["Authorization"] = f"Bearer {self.access_token}"
                        
                        return await self._make_request(
                            method=method,
                            endpoint=endpoint,
                            params=params,
                            json_data=json_data,
                            retry_on_auth_error=False,
                        )
                
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if e.response else str(e)
            logger.error(
                "Graph API request failed",
                extra={
                    "method": method,
                    "endpoint": endpoint,
                    "status_code": e.response.status_code if e.response else None,
                    "error": error_detail,
                },
            )
            raise SharePointClientError(
                f"Graph API request failed: {error_detail}"
            )
        except Exception as e:
            logger.error("Unexpected error in Graph API request", exc_info=True)
            raise SharePointClientError(f"Graph API request failed: {str(e)}")
    
    async def list_sites(self) -> List[Dict[str, Any]]:
        """
        List all SharePoint sites accessible to the authenticated user.
        
        Returns:
            List of site objects with id, name, webUrl, etc.
        """
        sites = []
        endpoint = "/sites"
        params = {"$select": "id,name,webUrl,displayName,description"}
        
        while True:
            response = await self._make_request("GET", endpoint, params=params)
            sites.extend(response.get("value", []))
            
            next_link = response.get("@odata.nextLink")
            if not next_link:
                break
            
            endpoint = next_link.replace(self.GRAPH_API_BASE, "")
            params = None
        
        return sites
    
    async def list_drives(self, site_id: str) -> List[Dict[str, Any]]:
        """
        List document libraries (drives) for a SharePoint site.
        
        Args:
            site_id: SharePoint site ID
            
        Returns:
            List of drive objects with id, name, webUrl, etc.
        """
        endpoint = f"/sites/{site_id}/drives"
        params = {"$select": "id,name,webUrl,description,driveType"}
        
        response = await self._make_request("GET", endpoint, params=params)
        return response.get("value", [])
    
    async def get_drive_items(
        self,
        drive_id: str,
        folder_path: str = "/",
        delta_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get items from a SharePoint drive with optional delta sync.
        
        Args:
            drive_id: SharePoint drive (document library) ID
            folder_path: Folder path within the drive (default: root)
            delta_token: Optional delta token for incremental sync
            
        Returns:
            Dictionary with items list and optional delta token
        """
        if delta_token:
            endpoint = f"/drives/{drive_id}/root/delta"
            params = {"token": delta_token}
        else:
            if folder_path == "/":
                endpoint = f"/drives/{drive_id}/root/children"
            else:
                endpoint = f"/drives/{drive_id}/root:/{folder_path.lstrip('/')}:/children"
            params = {
                "$select": "id,name,webUrl,size,lastModifiedDateTime,file,folder",
                "$top": 1000,
            }
        
        response = await self._make_request("GET", endpoint, params=params)
        
        items = response.get("value", [])
        next_link = response.get("@odata.nextLink")
        delta_link = response.get("@odata.deltaLink")
        
        while next_link:
            next_endpoint = next_link.replace(self.GRAPH_API_BASE, "")
            next_response = await self._make_request("GET", next_endpoint)
            items.extend(next_response.get("value", []))
            next_link = next_response.get("@odata.nextLink")
            delta_link = next_response.get("@odata.deltaLink")
        
        result = {"items": items}
        
        if delta_link:
            delta_token = delta_link.split("token=")[-1] if "token=" in delta_link else None
            result["delta_token"] = delta_token
        
        return result
    
    async def download_file(self, drive_id: str, item_id: str) -> bytes:
        """
        Download file content from SharePoint.
        
        Args:
            drive_id: SharePoint drive ID
            item_id: File item ID
            
        Returns:
            File content as bytes
        """
        endpoint = f"/drives/{drive_id}/items/{item_id}/content"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.GRAPH_API_BASE}/{endpoint.lstrip('/')}",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    timeout=60.0,
                )
                response.raise_for_status()
                return response.content
                
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if e.response else str(e)
            logger.error(
                "File download failed",
                extra={
                    "drive_id": drive_id,
                    "item_id": item_id,
                    "status_code": e.response.status_code if e.response else None,
                    "error": error_detail,
                },
            )
            raise SharePointClientError(f"File download failed: {error_detail}")
        except Exception as e:
            logger.error("Unexpected error during file download", exc_info=True)
            raise SharePointClientError(f"File download failed: {str(e)}")
