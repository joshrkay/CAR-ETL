"""API routes package."""
from .tenants import router as tenants_router
from .service_accounts import router as service_accounts_router

__all__ = ["tenants_router", "service_accounts_router"]
