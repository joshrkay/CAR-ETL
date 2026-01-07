"""JWT validation and claim extraction utilities for CAR Platform."""
import logging
from typing import Dict, Any, Optional, List
from jose import jwt, jwk
from jose.exceptions import JWTError, ExpiredSignatureError, JWTClaimsError

from .config import Auth0Config, get_auth0_config

logger = logging.getLogger(__name__)

# CAR Platform custom claim namespaces
TENANT_ID_CLAIM = "https://car.platform/tenant_id"
ROLES_CLAIM = "https://car.platform/roles"


class JWTValidationError(Exception):
    """Raised when JWT validation fails."""
    pass


class JWTClaims:
    """Extracted JWT claims with type safety."""
    
    def __init__(
        self,
        tenant_id: Optional[str],
        roles: List[str],
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        raw_claims: Optional[Dict[str, Any]] = None
    ):
        """Initialize JWT claims.
        
        Args:
            tenant_id: Tenant identifier from custom claim.
            roles: List of role strings from custom claim.
            user_id: Auth0 user ID (sub claim).
            email: User email address.
            raw_claims: Raw JWT payload for additional claims.
        """
        self.tenant_id = tenant_id
        self.roles = roles or []
        self.user_id = user_id
        self.email = email
        self.raw_claims = raw_claims or {}
    
    def has_role(self, role: str) -> bool:
        """Check if user has a specific role.
        
        Args:
            role: Role name to check.
        
        Returns:
            True if user has the role, False otherwise.
        """
        return role in self.roles
    
    def has_any_role(self, roles: List[str]) -> bool:
        """Check if user has any of the specified roles.
        
        Args:
            roles: List of role names to check.
        
        Returns:
            True if user has any of the roles, False otherwise.
        """
        return any(role in self.roles for role in roles)
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"JWTClaims(tenant_id={self.tenant_id}, "
            f"roles={self.roles}, "
            f"user_id={self.user_id})"
        )


class JWTValidator:
    """Validates JWTs and extracts CAR Platform custom claims."""
    
    def __init__(self, config: Optional[Auth0Config] = None):
        """Initialize JWT validator.
        
        Args:
            config: Auth0 configuration. If not provided, loads from environment.
        """
        self.config = config or get_auth0_config()
        self._jwks_cache: Optional[Dict[str, Any]] = None
    
    def _fetch_jwks(self) -> Dict[str, Any]:
        """Fetch JWKS from Auth0.
        
        Returns:
            JWKS dictionary.
        
        Raises:
            JWTValidationError: If JWKS fetch fails.
        """
        import httpx
        
        try:
            response = httpx.get(self.config.jwks_uri, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch JWKS: {e}")
            raise JWTValidationError(f"JWKS fetch failed: {e}") from e
    
    def _get_signing_key(self, token: str, jwks: Dict[str, Any]) -> Any:
        """Get signing key for token from JWKS.
        
        Args:
            token: JWT token string.
            jwks: JWKS dictionary.
        
        Returns:
            Signing key object.
        
        Raises:
            JWTValidationError: If key not found.
        """
        # Get unverified header to find key ID
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            
            if not kid:
                raise JWTValidationError("Token header missing 'kid' (key ID)")
            
            # Find the key in JWKS
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    return jwk.construct(key)
            
            raise JWTValidationError(f"Key with kid '{kid}' not found in JWKS")
        except JWTError as e:
            raise JWTValidationError(f"Failed to get signing key: {e}") from e
    
    def validate_token(
        self,
        token: str,
        audience: Optional[str] = None,
        verify_exp: bool = True
    ) -> Dict[str, Any]:
        """Validate JWT token and return payload.
        
        Args:
            token: JWT token string.
            audience: Expected audience (defaults to API identifier).
            verify_exp: Whether to verify token expiration.
        
        Returns:
            Decoded JWT payload.
        
        Raises:
            JWTValidationError: If validation fails.
        """
        try:
            # Fetch JWKS
            jwks = self._fetch_jwks()
            
            # Get signing key
            signing_key = self._get_signing_key(token, jwks)
            
            # Validate audience
            expected_audience = audience or self.config.api_identifier
            
            # Decode and verify token
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=[self.config.algorithm],
                audience=expected_audience,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_exp": verify_exp
                }
            )
            
            return payload
        except ExpiredSignatureError as e:
            logger.warning("JWT token has expired")
            raise JWTValidationError("Token has expired") from e
        except JWTClaimsError as e:
            logger.warning(f"JWT claims validation failed: {e}")
            raise JWTValidationError(f"Token claims validation failed: {e}") from e
        except JWTError as e:
            logger.error(f"JWT validation failed: {e}")
            raise JWTValidationError(f"JWT validation failed: {e}") from e
    
    def extract_claims(self, token: str) -> JWTClaims:
        """Validate token and extract CAR Platform custom claims.
        
        Checks for service account tokens first (before JWT validation),
        then validates as JWT if not a service account token.
        
        Args:
            token: JWT token string or service account token.
        
        Returns:
            JWTClaims object with extracted claims.
        
        Raises:
            JWTValidationError: If validation or claim extraction fails, or if token is revoked.
        """
        # Check if token is a service account token FIRST (before JWT validation)
        # Service account tokens are random strings, not JWTs
        try:
            from src.services.service_account_tokens import (
                get_service_account_token_service,
                ServiceAccountTokenError
            )
            token_service = get_service_account_token_service()
            token_record = token_service.validate_token(token)
            
            if token_record:
                # Token is a valid service account token
                # Update last_used and create JWTClaims from token metadata
                token_service.update_last_used(token_service._hash_token(token))
                
                # Create JWTClaims from service account token metadata
                return JWTClaims(
                    tenant_id=str(token_record.tenant_id),
                    roles=[token_record.role],  # Service account has single role
                    user_id=f"service-account-{token_record.token_id}",  # Service account identifier
                    email=None,
                    raw_claims={
                        "sub": f"service-account-{token_record.token_id}",
                        "https://car.platform/tenant_id": str(token_record.tenant_id),
                        "https://car.platform/roles": [token_record.role]
                    }
                )
        except ServiceAccountTokenError as e:
            # Token is revoked - fail validation immediately
            logger.warning(f"Revoked service account token attempted: {e}")
            raise JWTValidationError(f"Token has been revoked: {str(e)}") from e
        except Exception as e:
            # If service account token check fails, continue to JWT validation
            # This allows regular Auth0/Supabase JWT tokens to work
            logger.debug(f"Service account token check failed (trying JWT validation): {e}")
        
        # Not a service account token - validate as JWT
        payload = self.validate_token(token)
        
        # Extract custom claims from JWT
        tenant_id = payload.get(TENANT_ID_CLAIM)
        roles = payload.get(ROLES_CLAIM, [])
        
        # Validate roles is an array
        if not isinstance(roles, list):
            logger.warning(f"Invalid roles format in token, expected array, got {type(roles)}")
            roles = []
        
        # Extract standard claims
        user_id = payload.get("sub")
        email = payload.get("email")
        
        # Log missing tenant_id (warning, not error)
        if not tenant_id:
            logger.warning(f"Token missing tenant_id claim for user {user_id}")
        
        return JWTClaims(
            tenant_id=tenant_id,
            roles=roles,
            user_id=user_id,
            email=email,
            raw_claims=payload
        )


def get_jwt_validator(config: Optional[Auth0Config] = None) -> JWTValidator:
    """Get or create JWT validator instance."""
    return JWTValidator(config)
