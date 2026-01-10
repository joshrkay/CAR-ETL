"""Google Drive API client for file operations."""
import logging
import asyncio
from typing import List, Dict, Any, Optional, cast
import httpx
from src.connectors.google_drive.oauth import GoogleDriveOAuth, GoogleDriveOAuthError

logger = logging.getLogger(__name__)


class GoogleDriveClientError(Exception):
    """Error for Google Drive API operations."""
    pass


class TokenRevokedError(GoogleDriveClientError):
    """Token has been revoked and needs re-authentication."""
    pass


class RateLimitError(GoogleDriveClientError):
    """Rate limit exceeded."""
    pass


class GoogleDriveClient:
    """Client for Google Drive API operations."""
    
    DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
    
    def __init__(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        oauth_handler: Optional[GoogleDriveOAuth] = None,
    ):
        """
        Initialize Google Drive API client.
        
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
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Drive API with automatic token refresh and rate limit handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (relative to DRIVE_API_BASE)
            params: Query parameters
            json_data: JSON request body
            retry_on_auth_error: Whether to retry with refreshed token on 401
            max_retries: Maximum retry attempts for rate limits
            
        Returns:
            JSON response data
            
        Raises:
            GoogleDriveClientError: If request fails
            TokenRevokedError: If token is revoked
            RateLimitError: If rate limit exceeded after retries
        """
        url = f"{self.DRIVE_API_BASE}/{endpoint.lstrip('/')}"
        
        for attempt in range(max_retries):
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
                    
                    # Handle 401 - token expired or revoked
                    if response.status_code == 401:
                        if retry_on_auth_error and self.oauth_handler and self.refresh_token:
                            try:
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
                            except GoogleDriveOAuthError:
                                error_text = response.text.lower()
                                if "invalid_grant" in error_text or "revoked" in error_text:
                                    logger.error(
                                        "Token revoked",
                                        extra={"endpoint": endpoint},
                                    )
                                    raise TokenRevokedError("Token revoked, needs re-authentication")
                                raise
                        else:
                            error_text = response.text.lower()
                            if "invalid_grant" in error_text or "revoked" in error_text:
                                raise TokenRevokedError("Token revoked, needs re-authentication")
                            raise GoogleDriveClientError(f"Unauthorized: {response.text}")
                    
                    # Handle 429 - rate limit
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", "60"))
                        if attempt < max_retries - 1:
                            wait_time = min(retry_after * (2 ** attempt), 300)  # Cap at 5 minutes
                            logger.warning(
                                "Rate limit exceeded, retrying",
                                extra={
                                    "endpoint": endpoint,
                                    "attempt": attempt + 1,
                                    "wait_seconds": wait_time,
                                },
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            raise RateLimitError("Rate limit exceeded after retries")
                    
                    response.raise_for_status()
                    return cast(Dict[str, Any], response.json())
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    continue
                error_detail = e.response.text if e.response else str(e)
                logger.error(
                    "Drive API request failed",
                    extra={
                        "method": method,
                        "endpoint": endpoint,
                        "status_code": e.response.status_code if e.response else None,
                        "error": error_detail,
                    },
                )
                raise GoogleDriveClientError(
                    f"Drive API request failed: {error_detail}"
                )
            except (TokenRevokedError, RateLimitError):
                raise
            except Exception as e:
                logger.error("Unexpected error in Drive API request", exc_info=True)
                raise GoogleDriveClientError(f"Drive API request failed: {str(e)}")
        
        raise RateLimitError("Rate limit exceeded after all retries")
    
    async def list_drives(self, include_shared: bool = True) -> List[Dict[str, Any]]:
        """
        List all drives accessible to the authenticated user.
        
        Args:
            include_shared: Whether to include shared drives (team drives)
            
        Returns:
            List of drive objects with id, name, etc.
        """
        drives = []
        
        if include_shared:
            params = {
                "pageSize": 100,
                "fields": "nextPageToken, drives(id, name, kind)",
            }
            
            while True:
                response = await self._make_request("GET", "/drives", params=params)
                drives.extend(response.get("drives", []))
                
                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break
                
                params["pageToken"] = next_page_token
        
        return drives
    
    async def list_folders(
        self,
        drive_id: Optional[str] = None,
        parent_folder_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List folders in a drive or parent folder.
        
        Args:
            drive_id: Optional shared drive ID (for shared drives)
            parent_folder_id: Optional parent folder ID (default: root)
            
        Returns:
            List of folder objects with id, name, etc.
        """
        query_parts = ["mimeType='application/vnd.google-apps.folder'", "trashed=false"]
        
        if parent_folder_id:
            query_parts.append(f"'{parent_folder_id}' in parents")
        else:
            query_parts.append("'root' in parents")
        
        query = " and ".join(query_parts)
        
        params = {
            "q": query,
            "pageSize": 1000,
            "fields": "nextPageToken, files(id, name, mimeType, modifiedTime, size)",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        
        if drive_id:
            params["driveId"] = drive_id
            params["corpora"] = "drive"
        
        folders = []
        
        while True:
            response = await self._make_request("GET", "/files", params=params)
            folders.extend(response.get("files", []))
            
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
            
            params["pageToken"] = next_page_token
        
        return folders
    
    async def get_changes(
        self,
        page_token: Optional[str] = None,
        drive_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get changes using Google Drive Changes API for incremental sync.
        
        Args:
            page_token: Optional page token from previous changes request
            drive_id: Optional shared drive ID (for shared drives)
            
        Returns:
            Dictionary with changes list and next page token
        """
        params: Dict[str, Any] = {
            "pageSize": 1000,
            "fields": "nextPageToken, newStartPageToken, changes(file(id, name, mimeType, modifiedTime, size, trashed, parents), changeType, removed)",
        }
        
        if page_token:
            params["pageToken"] = page_token
        else:
            fields_value = params.get("fields", "")
            params["fields"] = fields_value + ", startPageToken"
        
        if drive_id:
            params["driveId"] = drive_id
            params["supportsAllDrives"] = "true"
            params["includeItemsFromAllDrives"] = "true"
        
        endpoint = "/changes"
        response = await self._make_request("GET", endpoint, params=params)
        
        changes = response.get("changes", [])
        next_page_token = response.get("nextPageToken")
        start_page_token = response.get("startPageToken") or response.get("newStartPageToken")
        
        result = {"changes": changes}
        
        if next_page_token:
            result["next_page_token"] = next_page_token
        
        if start_page_token:
            result["start_page_token"] = start_page_token
        
        return result
    
    async def get_start_page_token(self, drive_id: Optional[str] = None) -> str:
        """
        Get start page token for changes API.
        
        Args:
            drive_id: Optional shared drive ID
            
        Returns:
            Start page token string
        """
        params = {
            "fields": "startPageToken",
        }
        
        if drive_id:
            params["driveId"] = drive_id
            params["supportsAllDrives"] = "true"
        
        endpoint = "/changes/startPageToken"
        response = await self._make_request("GET", endpoint, params=params)
        
        token = response.get("startPageToken", "")
        return cast(str, token)
    
    async def download_file(self, file_id: str, drive_id: Optional[str] = None) -> bytes:
        """
        Download file content from Google Drive.
        
        Args:
            file_id: Google Drive file ID
            drive_id: Optional shared drive ID
            
        Returns:
            File content as bytes
        """
        params = {
            "alt": "media",
        }
        
        if drive_id:
            params["supportsAllDrives"] = "true"
        
        endpoint = f"/files/{file_id}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.DRIVE_API_BASE}/{endpoint.lstrip('/')}",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    params=params,
                    timeout=60.0,
                )
                response.raise_for_status()
                return bytes(response.content)
                
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if e.response else str(e)
            logger.error(
                "File download failed",
                extra={
                    "file_id": file_id,
                    "drive_id": drive_id,
                    "status_code": e.response.status_code if e.response else None,
                    "error": error_detail,
                },
            )
            raise GoogleDriveClientError(f"File download failed: {error_detail}")
        except Exception as e:
            logger.error("Unexpected error during file download", exc_info=True)
            raise GoogleDriveClientError(f"File download failed: {str(e)}")
