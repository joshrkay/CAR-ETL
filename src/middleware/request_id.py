"""Request ID middleware for request tracking."""
import uuid
from typing import Awaitable, Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to generate and track request IDs.
    
    Generates a UUID for each request and:
    - Stores it in request.state.request_id
    - Adds X-Request-ID header to all responses
    - Allows clients to provide their own request ID via X-Request-ID header
    """
    
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and add request ID."""
        # Check if client provided a request ID
        client_request_id = request.headers.get("X-Request-ID")
        
        if client_request_id:
            # Use client-provided request ID
            request_id = client_request_id
        else:
            # Generate new UUID
            request_id = str(uuid.uuid4())
        
        # Store in request state for use in handlers and logging
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response header
        if isinstance(response, Response):
            response.headers["X-Request-ID"] = request_id
        
        return response
