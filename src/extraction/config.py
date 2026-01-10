"""
Parser Configuration - Understanding Plane

Loads parser service configuration from environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ParserConfig(BaseSettings):
    """Configuration for parser services."""

    ragflow_api_url: str = ""
    ragflow_api_key: str = ""
    unstructured_api_url: str = ""
    unstructured_api_key: str = ""
    tika_api_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


_parser_config: ParserConfig | None = None


def get_parser_config() -> ParserConfig:
    """
    Get parser configuration singleton.

    Returns:
        ParserConfig instance
    """
    global _parser_config
    if _parser_config is None:
        _parser_config = ParserConfig()
    return _parser_config
