"""Supabase configuration and client setup."""
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SupabaseConfig(BaseSettings):
    """Supabase configuration from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Supabase Project Configuration
    project_url: str = Field(
        default="https://qifioafprrtkoiyylsqa.supabase.co",
        env="SUPABASE_URL",
        description="Supabase project URL (e.g., https://qifioafprrtkoiyylsqa.supabase.co)"
    )
    
    project_ref: str = Field(
        default="qifioafprrtkoiyylsqa",
        env="SUPABASE_PROJECT_REF",
        description="Supabase project reference ID"
    )
    
    # API Keys
    anon_key: str = Field(
        default="sb_publishable_PhKpWt7-UWeydaiqe99LDg_OSnuK7a0",
        env="SUPABASE_ANON_KEY",
        description="Supabase anonymous/public key (publishable key)"
    )
    
    service_role_key: str = Field(
        default="sb_secret_SDH3fH1Nl69oxRGNBPy91g_MhFHDYpm",
        env="SUPABASE_SERVICE_ROLE_KEY",
        description="Supabase service role key (secret key)"
    )
    
    # Database Connection (for direct PostgreSQL access)
    database_url: Optional[str] = Field(
        default=None,
        env="DATABASE_URL",
        description="PostgreSQL connection string for direct database access"
    )
    
    @property
    def api_url(self) -> str:
        """Get Supabase REST API URL."""
        if self.project_url:
            return f"{self.project_url}/rest/v1"
        return f"https://{self.project_ref}.supabase.co/rest/v1"
    
    @property
    def auth_url(self) -> str:
        """Get Supabase Auth API URL."""
        if self.project_url:
            return f"{self.project_url}/auth/v1"
        return f"https://{self.project_ref}.supabase.co/auth/v1"


def get_supabase_config() -> SupabaseConfig:
    """Get Supabase configuration instance."""
    return SupabaseConfig()
