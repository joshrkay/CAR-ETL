"""Auth0 configuration management from environment variables."""
import os
import logging
from typing import Optional
from pydantic import Field, field_validator, model_validator, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Auth0Config(BaseSettings):
    """Auth0 configuration loaded from environment variables."""

    # Auth0 Domain
    domain: str = Field(..., validation_alias="AUTH0_DOMAIN", description="Auth0 tenant domain")

    # API Configuration
    api_identifier: str = Field(
        default="https://api.car-platform.com",
        env="AUTH0_API_IDENTIFIER",
        description="Auth0 API identifier (audience)"
    )
    api_name: str = Field(
        default="CAR API",
        env="AUTH0_API_NAME",
        description="Auth0 API resource name"
    )

    # JWT Configuration
    algorithm: str = Field(
        default="RS256",
        env="AUTH0_ALGORITHM",
        description="JWT signing algorithm (RS256 for Auth0, ES256 for Supabase)"
    )
    jwks_uri: Optional[str] = Field(
        default=None,
        env="AUTH0_JWKS_URI",
        description="JWKS URI (auto-generated if not provided, or set to Supabase JWKS URI)"
    )

    # Management API Configuration
    management_client_id: str = Field(
        ...,
        validation_alias="AUTH0_MANAGEMENT_CLIENT_ID",
        description="Auth0 Management API client ID"
    )
    management_client_secret: str = Field(
        ...,
        validation_alias="AUTH0_MANAGEMENT_CLIENT_SECRET",
        description="Auth0 Management API client secret"
    )

    # Database Connection Configuration
    database_connection_name: str = Field(
        ...,
        validation_alias="AUTH0_DATABASE_CONNECTION_NAME",
        description="Auth0 database connection name"
    )

    # Retry Configuration
    max_retries: int = Field(
        default=3,
        env="AUTH0_MAX_RETRIES",
        description="Maximum number of retry attempts"
    )
    base_delay: float = Field(
        default=1.0,
        env="AUTH0_BASE_DELAY",
        description="Base delay in seconds for exponential backoff"
    )

    @model_validator(mode="after")
    def generate_jwks_uri(self) -> "Auth0Config":
        """Generate JWKS URI from domain if not provided.
        
        For Supabase, use: https://{project-ref}.supabase.co/auth/v1/.well-known/jwks.json
        For Auth0, use: https://{domain}/.well-known/jwks.json
        
        Also auto-detects Supabase and sets algorithm to ES256 if not explicitly set.
        """
        # Auto-detect Supabase and set algorithm if not explicitly set
        is_supabase = "supabase.co" in self.domain or self.domain.endswith(".supabase.co")
        if is_supabase and self.algorithm == "RS256" and not os.getenv("AUTH0_ALGORITHM"):
            # Auto-set ES256 for Supabase if algorithm wasn't explicitly set
            object.__setattr__(self, "algorithm", "ES256")
        
        if not self.jwks_uri:
            # Check if domain is a Supabase project reference
            if is_supabase:
                # Supabase JWKS URI format
                project_ref = self.domain.replace(".supabase.co", "").replace("https://", "").replace("http://", "")
                object.__setattr__(self, "jwks_uri", f"https://{project_ref}.supabase.co/auth/v1/.well-known/jwks.json")
            elif self.domain:
                # Auth0 JWKS URI format
                domain = self.domain.replace("https://", "").replace("http://", "")
                object.__setattr__(self, "jwks_uri", f"https://{domain}/.well-known/jwks.json")
        return self

    @field_validator("algorithm")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        """Validate JWT algorithm is supported (RS256 or ES256)."""
        supported_algorithms = ["RS256", "ES256"]
        if v not in supported_algorithms:
            raise ValueError(f"Algorithm must be one of: {', '.join(supported_algorithms)}")
        return v

    @property
    def management_api_url(self) -> str:
        """Get Management API base URL."""
        return f"https://{self.domain}/api/v2"

    @property
    def token_url(self) -> str:
        """Get OAuth token endpoint URL."""
        return f"https://{self.domain}/oauth/token"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


def get_auth0_config() -> Auth0Config:
    """Get Auth0 configuration instance."""
    return Auth0Config()
