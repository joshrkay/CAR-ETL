"""Auth configuration from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthConfig(BaseSettings):
    """Configuration for authentication."""

    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    supabase_jwt_secret: str
    app_env: str = "development"
    log_level: str = "INFO"

    # Rate limiting
    auth_rate_limit_max_attempts: int = 10
    auth_rate_limit_window_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables (e.g., SharePoint config)
    )

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env.lower() == "production"


def get_auth_config() -> AuthConfig:
    """Get auth configuration instance."""
    return AuthConfig()
