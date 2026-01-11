"""
Presidio Configuration - Understanding Plane

Loads Presidio configuration from environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class PresidioConfig(BaseSettings):
    """Configuration for Presidio redaction service."""

    analyzer_model: str = "en_core_web_lg"
    anonymizer_operators: str = "replace,hash,encrypt"
    default_anonymizer: str = "replace"
    supported_languages: str = "en"
    redaction_fail_mode: str = "strict"  # strict|permissive

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="PRESIDIO_",
        extra="ignore",  # Ignore extra environment variables (e.g., Supabase config)
    )

    @property
    def anonymizer_operators_list(self) -> list[str]:
        """Get anonymizer operators as list."""
        return [op.strip() for op in self.anonymizer_operators.split(",")]

    @property
    def supported_languages_list(self) -> list[str]:
        """Get supported languages as list."""
        return [lang.strip() for lang in self.supported_languages.split(",")]

    @property
    def is_strict_mode(self) -> bool:
        """Check if fail mode is strict (fail closed)."""
        return self.redaction_fail_mode.lower() == "strict"


def get_presidio_config() -> PresidioConfig:
    """Get Presidio configuration instance."""
    return PresidioConfig()
