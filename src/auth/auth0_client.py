"""Auth0 Management API client with retry logic and exponential backoff."""
import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import httpx
from jose import jwt, jwk
from jose.utils import base64url_decode

from .config import Auth0Config, get_auth0_config

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry logic."""

    max_retries: int
    base_delay: float


class Auth0TokenError(Exception):
    """Raised when Auth0 token acquisition fails."""

    pass


class Auth0APIError(Exception):
    """Raised when Auth0 API call fails."""

    pass


class Auth0ManagementClient:
    """Client for Auth0 Management API operations."""

    def __init__(self, config: Optional[Auth0Config] = None):
        """Initialize Auth0 Management API client."""
        self.config = config or get_auth0_config()
        self.retry_config = RetryConfig(
            max_retries=self.config.max_retries,
            base_delay=self.config.base_delay
        )
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _get_access_token(self) -> str:
        """Get or refresh Management API access token."""
        current_time = time.time()
        if self._access_token and current_time < self._token_expires_at:
            return self._access_token

        payload = {
            "client_id": self.config.management_client_id,
            "client_secret": self.config.management_client_secret,
            "audience": self.config.management_api_url,
            "grant_type": "client_credentials"
        }

        try:
            response = httpx.post(
                self.config.token_url,
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            token_data = response.json()
            self._access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 86400)
            self._token_expires_at = current_time + expires_in - 60
            return self._access_token
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text[:500] if e.response.text else "No error details"
            logger.error(
                "Failed to acquire Auth0 token",
                extra={
                    "status_code": e.response.status_code,
                    "response": error_detail
                }
            )
            raise Auth0TokenError(
                f"Token acquisition failed: {e.response.status_code} - {error_detail}"
            ) from e
        except httpx.RequestError as e:
            logger.error("Network error during token acquisition", extra={"error": str(e)})
            raise Auth0TokenError(f"Network error: {str(e)}") from e

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        return self.retry_config.base_delay * (2 ** attempt)

    def _make_request_with_retry(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any
    ) -> httpx.Response:
        """Make HTTP request with exponential backoff retry logic."""
        url = f"{self.config.management_api_url}/{endpoint.lstrip('/')}"
        token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        last_exception: Optional[Exception] = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                response = httpx.request(
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=30.0,
                    **kwargs
                )
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (401, 403):
                    self._access_token = None
                    if attempt < self.retry_config.max_retries:
                        continue
                if e.response.status_code < 500 or attempt >= self.retry_config.max_retries:
                    logger.error(
                        "Auth0 API request failed",
                        extra={
                            "method": method,
                            "url": url,
                            "status_code": e.response.status_code,
                            "attempt": attempt + 1
                        }
                    )
                    raise Auth0APIError(
                        f"API request failed: {e.response.status_code} - {e.response.text[:200]}"
                    ) from e
                last_exception = e
            except httpx.RequestError as e:
                if attempt >= self.retry_config.max_retries:
                    logger.error(
                        "Auth0 API network error",
                        extra={
                            "method": method,
                            "url": url,
                            "attempt": attempt + 1,
                            "error": str(e)
                        }
                    )
                    raise Auth0APIError(f"Network error: {str(e)}") from e
                last_exception = e

            if attempt < self.retry_config.max_retries:
                delay = self._calculate_backoff_delay(attempt)
                logger.warning(
                    "Retrying Auth0 API request",
                    extra={
                        "method": method,
                        "url": url,
                        "attempt": attempt + 1,
                        "delay": delay
                    }
                )
                time.sleep(delay)

        if last_exception:
            raise Auth0APIError(f"Request failed after {self.retry_config.max_retries} retries") from last_exception

        raise Auth0APIError("Unexpected retry loop exit")

    def get_user(self, user_id: str) -> Dict[str, Any]:
        """Get user by ID."""
        response = self._make_request_with_retry("GET", f"users/{user_id}")
        return response.json()

    def create_user(
        self,
        email: str,
        password: str,
        connection: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new user."""
        connection_name = connection or self.config.database_connection_name
        payload = {
            "email": email,
            "password": password,
            "connection": connection_name,
            "email_verified": False
        }
        response = self._make_request_with_retry("POST", "users", json=payload)
        return response.json()

    def update_user(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update user attributes."""
        response = self._make_request_with_retry("PATCH", f"users/{user_id}", json=updates)
        return response.json()

    def delete_user(self, user_id: str) -> None:
        """Delete a user."""
        self._make_request_with_retry("DELETE", f"users/{user_id}")

    def list_users(
        self,
        page: int = 0,
        per_page: int = 50,
        connection: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List users with pagination."""
        params: Dict[str, Any] = {
            "page": page,
            "per_page": per_page
        }
        if connection:
            params["connection"] = connection

        response = self._make_request_with_retry("GET", "users", params=params)
        return response.json()

    def verify_connectivity(self) -> bool:
        """Verify connectivity to Auth0 Management API."""
        try:
            self._get_access_token()
            return True
        except (Auth0TokenError, Auth0APIError) as e:
            logger.error("Auth0 connectivity check failed", extra={"error": str(e)})
            return False
