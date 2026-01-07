"""Example FastAPI application with auth middleware."""
from fastapi import FastAPI, Depends
from typing import Annotated
from src.auth.middleware import AuthMiddleware
from src.auth.models import AuthContext
from src.dependencies import get_current_user, require_role

app = FastAPI(title="CAR Platform API", version="1.0.0")

# Add authentication middleware
app.add_middleware(AuthMiddleware)


@app.get("/health")
async def health_check():
    """Health check endpoint (no auth required)."""
    return {"status": "healthy"}


@app.get("/me")
async def get_current_user_info(user: Annotated[AuthContext, Depends(get_current_user)]):
    """Get current authenticated user info."""
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "tenant_id": str(user.tenant_id),
        "roles": user.roles,
        "tenant_slug": user.tenant_slug,
    }


@app.get("/admin")
async def admin_endpoint(user: Annotated[AuthContext, Depends(require_role("Admin"))]):
    """Admin-only endpoint."""
    return {
        "message": "Admin access granted",
        "user_id": str(user.user_id),
    }
