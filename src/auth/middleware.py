"""FastAPI middleware for JWT authentication with custom claims."""
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from datetime import datetime
from uuid import UUID
import jwt
from typing import Optional, Union

from src.auth.config import AuthConfig, get_auth_config
from src.auth.models import AuthContext, AuthError
from src.auth.rate_limit import AuthRateLimiter, RateLimitError, get_rate_limiter


security = HTTPBearer(auto_error=False)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to validate JWT tokens and extract auth context."""

    def __init__(self, app, config: Optional[AuthConfig] = None):
        super().__init__(app)
        self.config = config or get_auth_config()
        self.rate_limiter = AuthRateLimiter(self.config)

    async def dispatch(self, request: Request, call_next):
        """Process request and validate JWT token."""
        if self._should_skip_auth(request):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        
        try:
            self.rate_limiter.check_rate_limit(client_ip)
        except RateLimitError as e:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": f"Too many authentication attempts. Retry after {e.retry_after} seconds",
                    "retry_after": e.retry_after,
                },
            )

        auth_error = await self._validate_token(request)
        if auth_error:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content=auth_error.model_dump(),
            )

        try:
            response = await call_next(request)
            if response.status_code < 400:
                self.rate_limiter.reset_rate_limit(client_ip)
            return response
        except Exception:
            return await call_next(request)

    def _should_skip_auth(self, request: Request) -> bool:
        """Check if authentication should be skipped for this path."""
        skip_paths = ["/health", "/docs", "/openapi.json", "/redoc", "/public"]
        return any(request.url.path.startswith(path) for path in skip_paths)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def _validate_token(self, request: Request) -> Optional[AuthError]:
        """
        Validate JWT token and attach AuthContext to request.state.
        
        Returns:
            AuthError if validation fails, None otherwise
        """
        credentials: Optional[HTTPAuthorizationCredentials] = await security(request)
        
        if not credentials:
            return AuthError.missing_token()

        token = credentials.credentials

        try:
            decoded = jwt.decode(
                token,
                self.config.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"verify_exp": True},
            )
        except jwt.ExpiredSignatureError:
            return AuthError.expired_token()
        except jwt.InvalidTokenError as e:
            return AuthError.invalid_token(str(e))
        
        # Double-check expiration (in case verify_exp didn't catch it)
        exp = decoded.get("exp")
        if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
            return AuthError.expired_token()

        auth_context = self._extract_auth_context(decoded)
        if isinstance(auth_context, AuthError):
            return auth_context

        request.state.auth = auth_context
        return None

    def _extract_auth_context(self, decoded: dict) -> Union[AuthContext, AuthError]:
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
            token_exp = datetime.fromtimestamp(exp)
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
