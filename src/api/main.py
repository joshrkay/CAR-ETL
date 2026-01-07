"""Main FastAPI application with tenant context middleware."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.middleware.tenant_context import TenantContextMiddleware
from src.api.routes import tenants, rbac_examples, example_jwt_usage, example_tenant_usage, audit_example
from src.api.routes.service_accounts import router as service_accounts_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup: Initialize audit logger
    try:
        from src.audit.logger_factory import get_audit_logger
        audit_logger = get_audit_logger()
        await audit_logger.start()
        logger.info("Audit logger started")
    except Exception as e:
        logger.warning(f"Failed to start audit logger: {e}. Audit logging may be unavailable.")
    
    yield
    
    # Shutdown: Stop audit logger
    try:
        from src.audit.logger_factory import get_audit_logger
        audit_logger = get_audit_logger()
        await audit_logger.stop()
        logger.info("Audit logger stopped")
    except Exception as e:
        logger.error(f"Error stopping audit logger: {e}", exc_info=True)


app = FastAPI(
    title="CAR Platform API",
    description="CAR AI Document Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware (configure as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add tenant context middleware (must be after CORS)
app.add_middleware(TenantContextMiddleware)

# Include routers
app.include_router(tenants.router)
app.include_router(rbac_examples.router)
app.include_router(example_jwt_usage.router)
app.include_router(example_tenant_usage.router)
app.include_router(audit_example.router)
app.include_router(service_accounts_router)


@app.get("/health")
async def health_check():
    """Health check endpoint (not protected by tenant middleware)."""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "CAR Platform API"}
