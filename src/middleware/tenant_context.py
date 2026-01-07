"""Tenant context middleware for multi-tenant request routing."""
import logging
import time
from typing import Callable, Optional

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from sqlalchemy.engine import Engine

from .auth import get_tenant_id_from_request
from src.services.tenant_resolver import TenantResolver, get_tenant_resolver

logger = logging.getLogger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Middleware that resolves tenant context and attaches database connection.
    
    This middleware:
    1. Intercepts all /api/* requests
    2. Extracts JWT from Authorization header
    3. Parses tenant_id from custom claim
    4. Looks up tenant database connection (with caching)
    5. Attaches connection to request.state.db
    6. Returns 401 for authentication/authorization errors
    """
    
    def __init__(
        self,
        app: ASGIApp,
        tenant_resolver: Optional[TenantResolver] = None
    ):
        """Initialize tenant context middleware.
        
        Args:
            app: ASGI application.
            tenant_resolver: Optional tenant resolver instance (for testing).
        """
        super().__init__(app)
        self.tenant_resolver = tenant_resolver or get_tenant_resolver()
    
    def _should_process_request(self, request: Request) -> bool:
        """Check if request should be processed by middleware.
        
        Args:
            request: FastAPI request object.
        
        Returns:
            True if request path starts with /api/, False otherwise.
        """
        return request.url.path.startswith("/api/")
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ):
        """Process request and attach tenant context.
        
        Args:
            request: FastAPI request object.
            call_next: Next middleware/handler in chain.
        
        Returns:
            Response from next handler or error response.
        """
        # Skip non-API requests
        if not self._should_process_request(request):
            return await call_next(request)
        
        start_time = time.time()
        
        try:
            # Extract and validate tenant_id from JWT
            # This will raise HTTPException if JWT is invalid or tenant_id format is invalid
            tenant_id = get_tenant_id_from_request(request)
            
            if not tenant_id:
                logger.warning(
                    f"Missing tenant_id in request: path={request.url.path}, "
                    f"method={request.method}"
                )
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Missing or invalid authentication token",
                        "error": "missing_tenant_id"
                    }
                )
            
            # Resolve tenant database connection
            tenant_engine = self.tenant_resolver.resolve_tenant_connection(tenant_id)
            
            if not tenant_engine:
                logger.warning(
                    f"Failed to resolve tenant connection: tenant_id={tenant_id}, "
                    f"path={request.url.path}"
                )
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Tenant not found or inactive",
                        "error": "tenant_not_found_or_inactive"
                    }
                )
            
            # Attach to request state
            request.state.db = tenant_engine
            request.state.tenant_id = tenant_id
            
            # Log tenant resolution (not secrets)
            elapsed = (time.time() - start_time) * 1000  # Convert to milliseconds
            logger.info(
                f"Tenant context resolved: tenant_id={tenant_id}, "
                f"path={request.url.path}, elapsed={elapsed:.2f}ms"
            )
            
            # Continue to next handler
            response = await call_next(request)
            return response
            
        except HTTPException as e:
            # Re-raise HTTP exceptions (already formatted)
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in tenant context middleware: {e}",
                exc_info=True
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"}
            )
