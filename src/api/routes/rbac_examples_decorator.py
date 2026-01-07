"""Example routes demonstrating RBAC decorator usage."""
from fastapi import APIRouter, Depends

from src.auth.decorators import requires_role, requires_any_role, requires_permission
from src.auth.jwt_validator import JWTClaims
from src.auth.dependencies import get_current_user_claims

router = APIRouter(prefix="/api/v1/rbac-decorator", tags=["rbac-decorator"])


# ============================================================================
# Decorator-based RBAC Examples
# ============================================================================

@router.post("/users")
@requires_role("Admin")
async def create_user(
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Create a new user (Admin only) - using decorator."""
    return {
        "message": "User created successfully",
        "user_id": "new-user-id",
        "created_by": claims.user_id
    }


@router.delete("/users/{user_id}")
@requires_role("admin")  # Case-insensitive
async def delete_user(
    user_id: str,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Delete a user (Admin only) - using decorator."""
    return {
        "message": f"User {user_id} deleted",
        "deleted_by": claims.user_id
    }


@router.get("/users")
@requires_role("Admin")
async def list_users(
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """List all users (Admin only) - using decorator."""
    return {
        "users": ["user1", "user2", "user3"],
        "count": 3
    }


@router.patch("/tenant/settings")
@requires_role("Admin")
async def modify_tenant_settings(
    settings: dict,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Modify tenant settings (Admin only) - using decorator."""
    return {
        "message": "Tenant settings updated",
        "tenant_id": claims.tenant_id,
        "updated_by": claims.user_id
    }


@router.get("/billing")
@requires_role("Admin")
async def access_billing(
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Access billing information (Admin only) - using decorator."""
    return {
        "billing": {
            "current_usage": 1000,
            "plan": "enterprise",
            "cost": 500.00
        },
        "tenant_id": claims.tenant_id
    }


# ============================================================================
# Multi-Role Decorator Examples
# ============================================================================

@router.post("/documents")
@requires_any_role(["Admin", "Analyst"])
async def upload_document(
    document_data: dict,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Upload a document (Analyst and Admin) - using decorator."""
    return {
        "message": "Document uploaded successfully",
        "document_id": "doc-123",
        "uploaded_by": claims.user_id,
        "tenant_id": claims.tenant_id
    }


@router.put("/documents/{document_id}")
@requires_any_role(["Admin", "Analyst"])
async def edit_document(
    document_id: str,
    document_data: dict,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Edit a document (Analyst and Admin) - using decorator."""
    return {
        "message": f"Document {document_id} updated",
        "updated_by": claims.user_id
    }


@router.delete("/documents/{document_id}")
@requires_any_role(["Admin", "Analyst"])
async def delete_document(
    document_id: str,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Delete a document (Analyst and Admin) - using decorator."""
    return {
        "message": f"Document {document_id} deleted",
        "deleted_by": claims.user_id
    }


@router.post("/ai/override")
@requires_any_role(["Admin", "Analyst"])
async def override_ai_decision(
    decision_data: dict,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Override AI decision (Analyst and Admin) - using decorator."""
    return {
        "message": "AI decision overridden",
        "overridden_by": claims.user_id
    }


# ============================================================================
# Permission-Based Decorator Examples
# ============================================================================

@router.post("/documents/upload")
@requires_permission("upload_document")
async def upload_document_permission(
    document_data: dict,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Upload document using permission decorator."""
    return {
        "message": "Document uploaded",
        "user_id": claims.user_id
    }


@router.get("/documents/{document_id}")
@requires_permission("view_document")
async def view_document(
    document_id: str,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """View a document (Viewer, Analyst, and Admin) - using permission decorator."""
    return {
        "document_id": document_id,
        "content": "Document content here",
        "viewed_by": claims.user_id
    }


@router.get("/documents/search")
@requires_permission("search_documents")
async def search_documents(
    query: str,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Search documents (Viewer, Analyst, and Admin) - using permission decorator."""
    return {
        "query": query,
        "results": ["doc1", "doc2", "doc3"],
        "count": 3
    }
