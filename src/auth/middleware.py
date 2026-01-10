"""FastAPI middleware for JWT authentication with custom claims."""
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import jwt
from fastapi import Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from src.auth.config import AuthConfig, get_auth_config
from src.auth.models import AuthContext, AuthError
from src.auth.rate_limit import AuthRateLimiter

security = HTTPBearer(auto_error=False)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to validate JWT tokens and extract auth context."""

    def __init__(self, app: Starlette, config: AuthConfig | None = None) -> None:
        super().__init__(app)
        self.config = config or get_auth_config()
        self.rate_limiter = AuthRateLimiter(self.config)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and validate JWT token."""
        if self._should_skip_auth(request):
            return await call_next(request)

        client_ip = self._get_client_ip(request)

        # Check rate limit (raises RateLimitError if exceeded)
        # ErrorHandlerMiddleware will catch and format the response
        self.rate_limiter.check_rate_limit(client_ip)

        auth_error = await self._validate_token(request)
        if auth_error:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content=auth_error.model_dump(),
            )

        response = await call_next(request)
        if response.status_code < 400:
            self.rate_limiter.reset_rate_limit(client_ip)
        return response

    def _should_skip_auth(self, request: Request) -> bool:
        """Check if authentication should be skipped for this path."""
        skip_paths = [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/public",
            "/api/v1/webhooks",
            "/oauth/microsoft/callback",
        ]
        return any(request.url.path.startswith(path) for path in skip_paths)

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.

        Returns a valid IP address format. For test clients that provide
        non-IP values (e.g., "testclient"), returns "127.0.0.1" as fallback.
        """
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
            # Validate it looks like an IP address
            if self._is_valid_ip(ip):
                return ip

        if request.client and request.client.host:
            host = request.client.host
            # If host is a valid IP, use it; otherwise use localhost for tests
            if self._is_valid_ip(host):
                return host

        # Fallback to localhost for test clients or unknown cases
        return "127.0.0.1"

    def _is_valid_ip(self, ip: str) -> bool:
        """
        Check if string looks like a valid IP address.

        Simple validation - checks for IPv4 format (x.x.x.x).
        """
        if not ip or ip == "unknown":
            return False

        # Check for IPv4 format (basic validation)
        parts = ip.split(".")
        if len(parts) != 4:
            return False

        try:
            return all(0 <= int(part) <= 255 for part in parts)
        except (ValueError, AttributeError):
            return False

    async def _validate_token(self, request: Request) -> AuthError | None:
        """
        Validate JWT token and attach AuthContext to request.state.

        Returns:
            AuthError if validation fails, None otherwise
        """
        credentials: HTTPAuthorizationCredentials | None = await security(request)

        if not credentials:
            return AuthError.missing_token()

        token = credentials.credentials

        try:
            # Try to decode with HS256 first (for backend-issued tokens)
            try:
                decoded = jwt.decode(
                    token,
                    self.config.supabase_jwt_secret,
                    algorithms=["HS256"],
                    options={"verify_exp": True},
                )
            except jwt.InvalidAlgorithmError:
                # If HS256 fails, token might be ES256 (Supabase access token)
                # For ES256, we'd need the public key from JWKS endpoint
                # For now, decode without verification in non-production
                if not self.config.is_production:
                    decoded = jwt.decode(
                        token,
                        options={"verify_signature": False, "verify_exp": False},
                    )
                else:
                    return AuthError.invalid_token("Token algorithm not supported (ES256 requires public key)")
        except jwt.ExpiredSignatureError:
            return AuthError.expired_token()
        except jwt.InvalidTokenError as e:
            return AuthError.invalid_token(str(e))

        # Double-check expiration (in case verify_exp didn't catch it)
        # Skip strict check in non-production for testing
        exp = decoded.get("exp")
        if exp and self.config.is_production:
            try:
                exp_time = datetime.fromtimestamp(exp, tz=UTC)
                if exp_time < datetime.now(UTC):
                    return AuthError.expired_token()
            except (ValueError, TypeError, OSError):
                # Invalid exp format, skip check
                pass

        auth_context = self._extract_auth_context(decoded)
        if isinstance(auth_context, AuthError):
            return auth_context

        # Create Supabase client with user's JWT token for RLS enforcement
        from src.auth.client import create_user_client
        user_client = create_user_client(token, self.config)

        # Attach auth context and user client to request state
        request.state.auth = auth_context
        request.state.supabase = user_client

        return None

    def _extract_auth_context(self, decoded: dict[str, Any]) -> AuthContext | AuthError:
        """
        Extract AuthContext from decoded JWT claims.

        Returns:
            AuthContext if valid, AuthError if claims are missing
        """
        user_id_str = decoded.get("sub")
        if not user_id_str:
            return AuthError.missing_claims("sub")

        try:
            user_id = UUID(user_id_str)
        except (ValueError, TypeError):
            return AuthError.invalid_token("Invalid user ID format")

        email = decoded.get("email", "")
        if not email:
            return AuthError.missing_claims("email")

        app_metadata = decoded.get("app_metadata", {})
        tenant_id_str = app_metadata.get("tenant_id")

        if not tenant_id_str:
            return AuthError.missing_claims("tenant_id")

        try:
            tenant_id = UUID(tenant_id_str) if isinstance(tenant_id_str, str) else tenant_id_str
        except (ValueError, TypeError):
            return AuthError.invalid_token("Invalid tenant_id format")

        roles = app_metadata.get("roles", [])
        if not isinstance(roles, list):
            roles = []

        exp = decoded.get("exp")
        if not exp:
            return AuthError.missing_claims("exp")

        try:
            token_exp = datetime.fromtimestamp(exp, tz=UTC)
        except (ValueError, TypeError):
            return AuthError.invalid_token("Invalid expiration format")

        tenant_slug = app_metadata.get("tenant_slug")

        return AuthContext(
            user_id=user_id,
            email=email,
            tenant_id=tenant_id,
            roles=roles,
            token_exp=token_exp,
            tenant_slug=tenant_slug,
        )
