"""JWT extraction and validation utilities for middleware."""
import logging
import uuid
from typing import Optional

from fastapi import Request, HTTPException, status

from src.auth.jwt_validator import JWTValidator, JWTClaims, JWTValidationError, get_jwt_validator

logger = logging.getLogger(__name__)


def extract_bearer_token(request: Request) -> Optional[str]:
    """Extract JWT token from Authorization header.
    
    Args:
        request: FastAPI request object.
    
    Returns:
        JWT token string, or None if not found.
    """
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None
    
    # Check for Bearer scheme
    if not authorization.startswith("Bearer "):
        return None
    
    # Extract token
    token = authorization[7:].strip()  # Remove "Bearer " prefix
    if not token:
        return None
    
    return token


def validate_jwt_and_extract_claims(
    token: str,
    jwt_validator: Optional[JWTValidator] = None
) -> JWTClaims:
    """Validate JWT token and extract claims.
    
    Args:
        token: JWT token string.
        jwt_validator: Optional JWT validator instance (for testing).
    
    Returns:
        JWTClaims object with extracted claims.
    
    Raises:
        HTTPException: If token validation fails.
    """
    validator = jwt_validator or get_jwt_validator()
    
    try:
        claims = validator.extract_claims(token)
        return claims
    except JWTValidationError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error during JWT validation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error"
        ) from e


def validate_tenant_id_format(tenant_id: str) -> bool:
    """Validate tenant_id is a valid UUID format.
    
    Args:
        tenant_id: Tenant identifier string.
    
    Returns:
        True if valid UUID format, False otherwise.
    """
    try:
        uuid.UUID(tenant_id)
        return True
    except (ValueError, TypeError):
        return False


def get_tenant_id_from_request(
    request: Request,
    jwt_validator: Optional[JWTValidator] = None
) -> Optional[str]:
    """Extract and validate tenant_id from JWT in request.
    
    Args:
        request: FastAPI request object.
        jwt_validator: Optional JWT validator instance (for testing).
    
    Returns:
        Tenant ID string (validated UUID format), or None if not found.
    
    Raises:
        HTTPException: If JWT validation fails or tenant_id format is invalid.
    """
    # Extract token
    token = extract_bearer_token(request)
    if not token:
        return None
    
    # Validate and extract claims
    claims = validate_jwt_and_extract_claims(token, jwt_validator)
    
    tenant_id = claims.tenant_id
    
    # Validate tenant_id format (must be UUID)
    if tenant_id and not validate_tenant_id_format(tenant_id):
        logger.warning(f"Invalid tenant_id format in JWT: {tenant_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant_id format in token (must be UUID)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return tenant_id
