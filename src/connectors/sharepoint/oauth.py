"""OAuth2 flow for Microsoft Graph API authentication."""
import logging
import os
from typing import Any, cast
from urllib.parse import urlencode
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)


class SharePointOAuthError(Exception):
    """OAuth-specific error for SharePoint authentication."""
    pass


class SharePointOAuth:
    """Handles OAuth2 flow for Microsoft Graph API."""

    # Microsoft OAuth endpoints
    AUTHORIZATION_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

    # Required scopes for SharePoint access
    REQUIRED_SCOPES = [
        "Files.Read.All",
        "Sites.Read.All",
        "offline_access",
    ]

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """
        Initialize SharePoint OAuth handler.

        Args:
            client_id: Azure AD application client ID
            client_secret: Azure AD application client secret
            redirect_uri: OAuth redirect URI (must match Azure AD registration)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    @classmethod
    def from_env(cls) -> "SharePointOAuth":
        """
        Create OAuth handler from environment variables.

        Environment variables:
            SHAREPOINT_CLIENT_ID: Azure AD application client ID
            SHAREPOINT_CLIENT_SECRET: Azure AD application client secret
            SHAREPOINT_REDIRECT_URI: OAuth redirect URI

        Returns:
            SharePointOAuth instance

        Raises:
            ValueError: If required environment variables are missing
        """
        client_id = os.getenv("SHAREPOINT_CLIENT_ID")
        client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
        redirect_uri = os.getenv("SHAREPOINT_REDIRECT_URI")

        if not all([client_id, client_secret, redirect_uri]):
            raise ValueError(
                "Missing required environment variables: "
                "SHAREPOINT_CLIENT_ID, SHAREPOINT_CLIENT_SECRET, SHAREPOINT_REDIRECT_URI"
            )

        # Type narrowing: after the check above, we know these are not None
        assert client_id is not None
        assert client_secret is not None
        assert redirect_uri is not None

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )

    def get_authorization_url(self, state: str | None = None) -> str:
        """
        Generate OAuth authorization URL.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Authorization URL for user redirect
        """
        if not state:
            state = str(uuid4())

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "response_mode": "query",
            "scope": " ".join(self.REQUIRED_SCOPES),
            "state": state,
        }

        return f"{self.AUTHORIZATION_URL}?{urlencode(params)}"

    async def exchange_code_for_tokens(
        self,
        code: str,
        state: str | None = None,
    ) -> dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from OAuth callback
            state: State parameter (should match authorization request)

        Returns:
            Dictionary containing access_token, refresh_token, expires_in, etc.

        Raises:
            SharePointOAuthError: If token exchange fails
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.TOKEN_URL,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0,
                )
                response.raise_for_status()
                token_data = response.json()

                if "access_token" not in token_data:
                    raise SharePointOAuthError("Token response missing access_token")

                return cast(dict[str, Any], token_data)

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if e.response else str(e)
            logger.error(
                "Token exchange failed",
                extra={
                    "status_code": e.response.status_code if e.response else None,
                    "error": error_detail,
                },
            )
            raise SharePointOAuthError(f"Token exchange failed: {error_detail}")
        except Exception as e:
            logger.error("Unexpected error during token exchange", exc_info=True)
            raise SharePointOAuthError(f"Token exchange failed: {str(e)}")

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Refresh token from previous OAuth flow

        Returns:
            Dictionary containing new access_token, refresh_token, expires_in, etc.

        Raises:
            SharePointOAuthError: If token refresh fails
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.TOKEN_URL,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0,
                )
                response.raise_for_status()
                token_data = response.json()

                if "access_token" not in token_data:
                    raise SharePointOAuthError("Token response missing access_token")

                return cast(dict[str, Any], token_data)

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if e.response else str(e)
            logger.error(
                "Token refresh failed",
                extra={
                    "status_code": e.response.status_code if e.response else None,
                    "error": error_detail,
                },
            )
            raise SharePointOAuthError(f"Token refresh failed: {error_detail}")
        except Exception as e:
            logger.error("Unexpected error during token refresh", exc_info=True)
            raise SharePointOAuthError(f"Token refresh failed: {str(e)}")
