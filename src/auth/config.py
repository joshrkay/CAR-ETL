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
    
    def validate_environment(self) -> list[str]:
        """
        Validate all required environment variables are set and not placeholders.
        
        Returns:
            List of validation error messages (empty if validation passes)
        """
        errors: list[str] = []
        
        # Common placeholder values to reject
        placeholder_values = [
            "your-project.supabase.co",
            "your_anon_key_here",
            "your_service_role_key_here",
            "your_jwt_secret_here",
            "your-anon-key",
            "your-service-key",
            "your-jwt-secret",
            "REPLACE_ME",
            "CHANGE_ME",
            "TODO",
            "",
        ]
        
        # Required variables and their display names
        required_vars = {
            "supabase_url": "SUPABASE_URL",
            "supabase_anon_key": "SUPABASE_ANON_KEY",
            "supabase_service_key": "SUPABASE_SERVICE_KEY",
            "supabase_jwt_secret": "SUPABASE_JWT_SECRET",
        }
        
        for attr_name, env_name in required_vars.items():
            value = getattr(self, attr_name, None)
            
            # Check if missing
            if value is None:
                errors.append(f"{env_name} is not set")
                continue
            
            # Convert to string for comparison
            value_str = str(value).strip()
            
            # Check if empty
            if not value_str:
                errors.append(f"{env_name} is empty")
                continue
            
            # Check if placeholder
            if value_str.lower() in [p.lower() for p in placeholder_values]:
                errors.append(f"{env_name} contains placeholder value: '{value_str}'")
                continue
        
        return errors


def get_auth_config() -> AuthConfig:
    """Get auth configuration instance."""
    return AuthConfig()
