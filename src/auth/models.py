"""Pydantic models for authentication."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AuthContext(BaseModel):
    """Authentication context attached to request state."""

    user_id: UUID = Field(..., description="User UUID from JWT sub claim")
    email: str = Field(..., description="User email address")
    tenant_id: UUID = Field(..., description="Tenant UUID from app_metadata")
    roles: list[str] = Field(default_factory=list, description="User roles")
    token_exp: datetime = Field(..., description="Token expiration timestamp")
    tenant_slug: str | None = Field(None, description="Tenant slug from app_metadata")

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles

    def has_any_role(self, roles: list[str]) -> bool:
        """Check if user has any of the specified roles."""
        return any(role in self.roles for role in roles)


class AuthError(BaseModel):
    """Authentication error response model."""

    code: str = Field(..., description="Error code (MISSING_TOKEN, INVALID_TOKEN, etc.)")
    message: str = Field(..., description="Human-readable error message")

    @classmethod
    def missing_token(cls) -> "AuthError":
        """Create error for missing Authorization header."""
        return cls(
            code="MISSING_TOKEN",
            message="Authorization header is required",
        )

    @classmethod
    def invalid_token(cls, reason: str = "Invalid token signature or format") -> "AuthError":
        """Create error for invalid token."""
        return cls(
            code="INVALID_TOKEN",
            message=reason,
        )

    @classmethod
    def expired_token(cls) -> "AuthError":
        """Create error for expired token."""
        return cls(
            code="EXPIRED_TOKEN",
            message="Token has expired",
        )

    @classmethod
    def missing_claims(cls, missing: str) -> "AuthError":
        """Create error for missing required claims."""
        return cls(
            code="MISSING_CLAIMS",
            message=f"Missing required claim: {missing}",
        )
