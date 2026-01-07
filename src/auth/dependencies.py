"""FastAPI dependencies for JWT authentication."""
import logging
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .jwt_validator import JWTValidator, JWTClaims, JWTValidationError, get_jwt_validator

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user_claims(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> JWTClaims:
    """FastAPI dependency to extract and validate JWT claims.
    
    Args:
        credentials: HTTP Bearer token credentials from request header.
        jwt_validator: Optional JWT validator instance (for testing).
    
    Returns:
        JWTClaims object with tenant_id, roles, and user information.
    
    Raises:
        HTTPException: If token is invalid, expired, or missing claims.
    """
    validator = jwt_validator or get_jwt_validator()
    
    try:
        # Extract token from Bearer scheme
        token = credentials.credentials
        
        # Validate and extract claims
        claims = validator.extract_claims(token)
        
        # Log authentication
        logger.info(
            f"User authenticated: user_id={claims.user_id}, "
            f"tenant_id={claims.tenant_id}, roles={claims.roles}"
        )
        
        return claims
    except JWTValidationError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error during JWT validation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error"
        ) from e


def require_role(required_role: str):
    """Create dependency that requires a specific role.
    
    Args:
        required_role: Role name required for access.
    
    Returns:
        Dependency function that checks role.
    """
    async def role_checker(claims: JWTClaims = Security(get_current_user_claims)) -> JWTClaims:
        """Check if user has required role."""
        if not claims.has_role(required_role):
            logger.warning(
                f"Access denied: user_id={claims.user_id} "
                f"missing required role '{required_role}'"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {required_role}"
            )
        return claims
    
    return role_checker


def require_any_role(required_roles: list[str]):
    """Create dependency that requires any of the specified roles.
    
    Args:
        required_roles: List of role names (user must have at least one).
    
    Returns:
        Dependency function that checks roles.
    """
    async def roles_checker(claims: JWTClaims = Security(get_current_user_claims)) -> JWTClaims:
        """Check if user has any of the required roles."""
        if not claims.has_any_role(required_roles):
            logger.warning(
                f"Access denied: user_id={claims.user_id} "
                f"missing required roles: {required_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required one of roles: {', '.join(required_roles)}"
            )
        return claims
    
    return roles_checker
