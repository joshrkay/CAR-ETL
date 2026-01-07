"""Service account token management endpoints."""
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.auth.dependencies import get_current_user_claims
from src.auth.decorators import RequiresRole
from src.auth.jwt_validator import JWTClaims
from src.services.service_account_tokens import (
    ServiceAccountTokenService,
    ServiceAccountTokenError,
    get_service_account_token_service
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/service-accounts", tags=["service-accounts"])


class CreateTokenRequest(BaseModel):
    """Request model for creating a service account token."""
    
    name: str = Field(..., description="Token name/description", min_length=1, max_length=255)
    role: str = Field(..., description="Role to assign (admin, analyst, ingestion, or viewer)", pattern="^(admin|analyst|viewer|ingestion)$")


class TokenResponse(BaseModel):
    """Response model for token creation."""
    
    token_id: str
    token: str  # Plain text token (only shown once)
    name: str
    role: str
    tenant_id: str
    created_at: str


class TokenMetadata(BaseModel):
    """Token metadata response model."""
    
    token_id: str
    name: str
    role: str
    created_by: str
    created_at: str
    last_used: Optional[str]
    is_revoked: bool
    revoked_at: Optional[str]


@router.post("/tokens", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@RequiresRole('Admin')
async def create_token(
    request: CreateTokenRequest,
    claims: JWTClaims = Depends(get_current_user_claims),
    token_service: ServiceAccountTokenService = Depends(get_service_account_token_service)
) -> TokenResponse:
    """Create a new service account API token.
    
    Uses OAuth Client Credentials flow to generate a long-lived token
    scoped to the tenant with the specified role.
    
    Args:
        request: Token creation request.
        claims: Current user JWT claims.
        token_service: Service account token service.
    
    Returns:
        Token response with token_id and plain text token.
    
    Raises:
        HTTPException: If token creation fails.
    """
    if not claims.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing tenant_id in token claims"
        )
    
    try:
        result = token_service.create_token(
            tenant_id=claims.tenant_id,
            name=request.name,
            role=request.role,
            created_by=claims.user_id or "unknown"
        )
        
        return TokenResponse(**result)
    except ServiceAccountTokenError as e:
        logger.error(f"Failed to create service account token: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error creating token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create service account token"
        )


@router.get("/tokens", response_model=List[TokenMetadata])
@RequiresRole('Admin')
async def list_tokens(
    claims: JWTClaims = Depends(get_current_user_claims),
    token_service: ServiceAccountTokenService = Depends(get_service_account_token_service)
) -> List[TokenMetadata]:
    """List all service account tokens for the tenant.
    
    Admin users can view all tokens for their tenant.
    
    Args:
        claims: Current user JWT claims.
        token_service: Service account token service.
    
    Returns:
        List of token metadata.
    
    Raises:
        HTTPException: If listing fails.
    """
    if not claims.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing tenant_id in token claims"
        )
    
    try:
        tokens = token_service.list_tokens(tenant_id=claims.tenant_id)
        return [TokenMetadata(**token) for token in tokens]
    except Exception as e:
        logger.error(f"Failed to list tokens: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list service account tokens"
        )


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
@RequiresRole('Admin')
async def revoke_token(
    token_id: str,
    claims: JWTClaims = Depends(get_current_user_claims),
    token_service: ServiceAccountTokenService = Depends(get_service_account_token_service)
) -> None:
    """Revoke a service account token.
    
    Revoked tokens immediately fail authentication on subsequent API calls.
    
    Args:
        token_id: Token identifier (UUID).
        claims: Current user JWT claims.
        token_service: Service account token service.
    
    Raises:
        HTTPException: If token not found or revocation fails.
    """
    if not claims.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing tenant_id in token claims"
        )
    
    try:
        token_service.revoke_token(
            token_id=token_id,
            tenant_id=claims.tenant_id,
            revoked_by=claims.user_id or "unknown"
        )
    except ServiceAccountTokenError as e:
        logger.error(f"Failed to revoke token: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error revoking token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke service account token"
        )
