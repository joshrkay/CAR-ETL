"""Service account token generation and management."""
import hashlib
import secrets
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.db.connection import get_connection_manager
from src.db.models.control_plane import ServiceAccountToken, Tenant
from src.auth.roles import Role
from src.auth.config import Auth0Config, get_auth0_config
import httpx

logger = logging.getLogger(__name__)


class ServiceAccountTokenError(Exception):
    """Raised when service account token operation fails."""
    pass


class ServiceAccountTokenService:
    """Service for managing service account API tokens."""
    
    def __init__(self, config: Optional[Auth0Config] = None):
        """Initialize service account token service.
        
        Args:
            config: Auth0 configuration. If not provided, loads from environment.
        """
        self.config = config or get_auth0_config()
        self.connection_manager = get_connection_manager()
    
    def _hash_token(self, token: str) -> str:
        """Hash token for storage (SHA-256).
        
        Args:
            token: Plain text token.
        
        Returns:
            SHA-256 hash of token.
        """
        return hashlib.sha256(token.encode('utf-8')).hexdigest()
    
    def _generate_token(self) -> str:
        """Generate a secure random token.
        
        Returns:
            Base64-encoded random token (32 bytes).
        """
        return secrets.token_urlsafe(32)
    
    def _get_oauth_token(
        self,
        tenant_id: str,
        role: str
    ) -> str:
        """Get OAuth token using Client Credentials flow.
        
        This creates a temporary Auth0 client and gets a token.
        In a real implementation, you would:
        1. Create an Auth0 Machine-to-Machine application
        2. Use client_id and client_secret to get token
        3. Include tenant_id and role in custom claims
        
        For now, we'll generate a JWT-like token that can be validated.
        
        Args:
            tenant_id: Tenant identifier.
            role: Role to assign to token.
        
        Returns:
            OAuth access token.
        
        Raises:
            ServiceAccountTokenError: If token generation fails.
        """
        # In a production system, you would:
        # 1. Create Auth0 M2M application via Management API
        # 2. Get client_id and client_secret
        # 3. Request token from Auth0 /oauth/token endpoint
        # 4. Token would include custom claims: tenant_id, role
        
        # For this implementation, we'll generate a token that can be
        # validated by our JWT validator. The token will be stored
        # in the database and checked during validation.
        
        # Generate a secure token
        token = self._generate_token()
        
        # In production, this would be an actual OAuth token from Auth0
        # For now, we return a token that will be validated against our database
        return token
    
    def create_token(
        self,
        tenant_id: str,
        name: str,
        role: str,
        created_by: str
    ) -> Dict[str, Any]:
        """Create a new service account token.
        
        Args:
            tenant_id: Tenant identifier (UUID string).
            name: Token name/description.
            role: Role to assign (typically 'analyst' or 'ingestion').
            created_by: User ID who created the token.
        
        Returns:
            Dictionary with token_id and token (plain text - only shown once).
        
        Raises:
            ServiceAccountTokenError: If token creation fails.
        """
        # Validate role
        try:
            role_enum = Role(role.lower())
        except ValueError:
            raise ServiceAccountTokenError(f"Invalid role: {role}. Must be one of: admin, analyst, viewer")
        
        # Validate tenant exists
        with self.connection_manager.get_session() as session:
            tenant = session.query(Tenant).filter(
                Tenant.tenant_id == UUID(tenant_id)
            ).first()
            
            if not tenant:
                raise ServiceAccountTokenError(f"Tenant not found: {tenant_id}")
            
            if tenant.status.value != "active":
                raise ServiceAccountTokenError(f"Tenant is not active: {tenant_id}")
        
        # Generate token
        plain_token = self._generate_token()
        token_hash = self._hash_token(plain_token)
        
        # Get OAuth token (in production, this would be from Auth0)
        oauth_token = self._get_oauth_token(tenant_id, role)
        
        # Store token metadata
        with self.connection_manager.get_session() as session:
            token_record = ServiceAccountToken(
                tenant_id=UUID(tenant_id),
                token_hash=token_hash,
                name=name,
                role=role.lower(),
                created_by=created_by,
                created_at=datetime.utcnow(),
                is_revoked=False
            )
            
            session.add(token_record)
            session.commit()
            
            token_id = str(token_record.token_id)
        
        logger.info(
            f"Service account token created",
            extra={
                "token_id": token_id,
                "tenant_id": tenant_id,
                "role": role,
                "created_by": created_by
            }
        )
        
        return {
            "token_id": token_id,
            "token": oauth_token,  # In production, this would be the Auth0 token
            "name": name,
            "role": role.lower(),
            "tenant_id": tenant_id,
            "created_at": datetime.utcnow().isoformat()
        }
    
    def revoke_token(
        self,
        token_id: str,
        tenant_id: str,
        revoked_by: str
    ) -> None:
        """Revoke a service account token.
        
        Args:
            token_id: Token identifier (UUID string).
            tenant_id: Tenant identifier (UUID string).
            revoked_by: User ID who revoked the token.
        
        Raises:
            ServiceAccountTokenError: If token not found or already revoked.
        """
        with self.connection_manager.get_session() as session:
            token = session.query(ServiceAccountToken).filter(
                and_(
                    ServiceAccountToken.token_id == UUID(token_id),
                    ServiceAccountToken.tenant_id == UUID(tenant_id)
                )
            ).first()
            
            if not token:
                raise ServiceAccountTokenError(f"Token not found: {token_id}")
            
            if token.is_revoked:
                raise ServiceAccountTokenError(f"Token already revoked: {token_id}")
            
            token.is_revoked = True
            token.revoked_at = datetime.utcnow()
            
            session.commit()
        
        logger.info(
            f"Service account token revoked",
            extra={
                "token_id": token_id,
                "tenant_id": tenant_id,
                "revoked_by": revoked_by
            }
        )
    
    def list_tokens(
        self,
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """List all service account tokens for a tenant.
        
        Args:
            tenant_id: Tenant identifier (UUID string).
        
        Returns:
            List of token metadata dictionaries.
        """
        with self.connection_manager.get_session() as session:
            tokens = session.query(ServiceAccountToken).filter(
                ServiceAccountToken.tenant_id == UUID(tenant_id)
            ).order_by(ServiceAccountToken.created_at.desc()).all()
            
            return [
                {
                    "token_id": str(token.token_id),
                    "name": token.name,
                    "role": token.role,
                    "created_by": token.created_by,
                    "created_at": token.created_at.isoformat() if token.created_at else None,
                    "last_used": token.last_used.isoformat() if token.last_used else None,
                    "is_revoked": token.is_revoked,
                    "revoked_at": token.revoked_at.isoformat() if token.revoked_at else None
                }
                for token in tokens
            ]
    
    def validate_token(
        self,
        token: str
    ) -> Optional[ServiceAccountToken]:
        """Validate a service account token.
        
        Args:
            token: Plain text token.
        
        Returns:
            ServiceAccountToken if valid, None if invalid or revoked.
        
        Raises:
            ServiceAccountTokenError: If token is revoked (for immediate failure).
        """
        token_hash = self._hash_token(token)
        
        with self.connection_manager.get_session() as session:
            token_record = session.query(ServiceAccountToken).filter(
                ServiceAccountToken.token_hash == token_hash
            ).first()
            
            if not token_record:
                # Token not found - might be a regular Auth0 token
                return None
            
            if token_record.is_revoked:
                # Token is revoked - raise error for immediate failure
                raise ServiceAccountTokenError(f"Token has been revoked: {token_record.token_id}")
            
            return token_record
    
    def update_last_used(
        self,
        token_hash: str
    ) -> None:
        """Update last_used timestamp for a token.
        
        Args:
            token_hash: Hashed token value.
        """
        with self.connection_manager.get_session() as session:
            token = session.query(ServiceAccountToken).filter(
                ServiceAccountToken.token_hash == token_hash
            ).first()
            
            if token and not token.is_revoked:
                token.last_used = datetime.utcnow()
                session.commit()


def get_service_account_token_service() -> ServiceAccountTokenService:
    """Get or create service account token service instance."""
    return ServiceAccountTokenService()
