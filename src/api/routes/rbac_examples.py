"""Example routes demonstrating RBAC enforcement."""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from src.auth.decorators import requires_role, requires_permission
from src.auth.dependencies import get_current_user_claims
from src.auth.roles import Role, Permission
from src.auth.jwt_validator import JWTClaims

router = APIRouter(prefix="/api/v1/rbac-examples", tags=["rbac-examples"])


# ============================================================================
# Admin Role Examples
# ============================================================================

@router.post("/users")
@requires_role("Admin")
async def create_user(
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Create a new user (Admin only).
    
    Admin role can: create/delete users, modify tenant settings, 
    access billing, all document operations.
    """
    return {
        "message": "User created successfully",
        "user_id": "new-user-id",
        "created_by": claims.user_id
    }


@router.delete("/users/{user_id}")
@requires_role("Admin")
async def delete_user(
    user_id: str,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Delete a user (Admin only)."""
    return {
        "message": f"User {user_id} deleted",
        "deleted_by": claims.user_id
    }


@router.get("/users")
@requires_role("Admin")
async def list_users(
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """List all users (Admin only)."""
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
    """Modify tenant settings (Admin only)."""
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
    """Access billing information (Admin only)."""
    return {
        "billing": {
            "current_usage": 1000,
            "plan": "enterprise",
            "cost": 500.00
        },
        "tenant_id": claims.tenant_id
    }


# ============================================================================
# Analyst Role Examples
# ============================================================================

@router.post("/documents")
@requires_permission("upload_document")
async def upload_document(
    document_data: dict,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Upload a document (Analyst and Admin).
    
    Analyst role can: upload/edit documents, override AI decisions, 
    search, cannot manage users.
    """
    return {
        "message": "Document uploaded successfully",
        "document_id": "doc-123",
        "uploaded_by": claims.user_id,
        "tenant_id": claims.tenant_id
    }


@router.put("/documents/{document_id}")
@requires_permission("edit_document")
async def edit_document(
    document_id: str,
    document_data: dict,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Edit a document (Analyst and Admin)."""
    return {
        "message": f"Document {document_id} updated",
        "updated_by": claims.user_id
    }


@router.delete("/documents/{document_id}")
@requires_permission("delete_document")
async def delete_document(
    document_id: str,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Delete a document (Analyst and Admin)."""
    return {
        "message": f"Document {document_id} deleted",
        "deleted_by": claims.user_id
    }


@router.post("/ai/override")
@requires_permission("override_ai_decision")
async def override_ai_decision(
    decision_data: dict,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Override AI decision (Analyst and Admin)."""
    return {
        "message": "AI decision overridden",
        "overridden_by": claims.user_id
    }


@router.get("/documents/search")
@requires_permission("search_documents")
async def search_documents(
    query: str,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Search documents (Analyst, Admin, and Viewer)."""
    return {
        "query": query,
        "results": ["doc1", "doc2", "doc3"],
        "count": 3
    }


# ============================================================================
# Viewer Role Examples
# ============================================================================

@router.get("/documents/{document_id}")
@requires_permission("view_document")
async def view_document(
    document_id: str,
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """View a document (Viewer, Analyst, and Admin).
    
    Viewer role can: search and view documents only, no edit capabilities.
    """
    return {
        "document_id": document_id,
        "content": "Document content here",
        "viewed_by": claims.user_id
    }


# ============================================================================
# Multi-Role Examples
# ============================================================================

@router.get("/documents")
@requires_role("Viewer", "Analyst", "Admin")
async def list_documents(
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """List documents (all roles can access)."""
    return {
        "documents": ["doc1", "doc2", "doc3"],
        "count": 3
    }


# ============================================================================
# Permission-Based Examples
# ============================================================================

@router.get("/tenant/settings")
@requires_permission("view_tenant_settings")
async def view_tenant_settings(
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """View tenant settings (all roles can view)."""
    return {
        "tenant_id": claims.tenant_id,
        "settings": {
            "name": "Example Tenant",
            "environment": "production"
        }
    }
