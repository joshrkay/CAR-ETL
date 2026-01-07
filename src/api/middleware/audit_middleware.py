"""Middleware to automatically log API requests to audit trail."""
import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ...audit.service import audit_log
from ...auth.jwt_validator import JWTClaims
from ...middleware.auth import get_tenant_id_from_request

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests to immutable audit trail.
    
    This middleware automatically logs all requests to the audit trail,
    extracting user_id and tenant_id from JWT claims.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log to audit trail.
        
        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in chain.
        
        Returns:
            HTTP response.
        """
        start_time = time.time()
        
        # Extract user info from request (if available)
        user_id: str | None = None
        tenant_id: str | None = None
        
        try:
            # Try to get tenant_id from request state (set by tenant context middleware)
            if hasattr(request.state, 'tenant_id'):
                tenant_id = request.state.tenant_id
            
            # Try to get user_id from JWT claims (if available)
            if hasattr(request.state, 'claims'):
                claims: JWTClaims = request.state.claims
                user_id = claims.user_id
                if not tenant_id:
                    tenant_id = claims.tenant_id
        except Exception as e:
            logger.debug(f"Could not extract user/tenant info for audit: {e}")
        
        # Process request
        response = await call_next(request)
        
        # Calculate request duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log to audit trail (async, non-blocking)
        if user_id and tenant_id:
            try:
                await audit_log(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    action_type=f"api.{request.method.lower()}.{request.url.path.replace('/', '.').strip('.')}",
                    resource_id=None,
                    request=request,
                    additional_metadata={
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 2)
                    }
                )
            except Exception as e:
                # Never fail request due to audit logging
                logger.debug(f"Failed to log request to audit trail: {e}")
        
        return response
