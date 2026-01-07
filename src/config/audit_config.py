"""Configuration for audit logging (Supabase or S3 storage)."""
from typing import Optional, Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuditConfig(BaseSettings):
    """Audit logging configuration from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Storage Backend Selection
    audit_storage_backend: Literal["supabase", "s3"] = Field(
        default="supabase",
        env="AUDIT_STORAGE_BACKEND",
        description="Storage backend: 'supabase' (PostgreSQL) or 's3' (AWS S3)"
    )
    
    # S3 Configuration (optional, only if using S3 backend)
    audit_s3_bucket: Optional[str] = Field(
        default=None,
        env="AUDIT_S3_BUCKET",
        description="S3 bucket name for audit logs (required if using S3 backend)"
    )
    
    audit_s3_region: str = Field(
        default="us-east-1",
        env="AUDIT_S3_REGION",
        description="AWS region for audit log S3 bucket"
    )
    
    aws_access_key_id: Optional[str] = Field(
        default=None,
        env="AWS_ACCESS_KEY_ID",
        description="AWS access key ID for S3 access"
    )
    
    aws_secret_access_key: Optional[str] = Field(
        default=None,
        env="AWS_SECRET_ACCESS_KEY",
        description="AWS secret access key for S3 access"
    )
    
    # Retention Configuration
    audit_retention_years: int = Field(
        default=7,
        env="AUDIT_RETENTION_YEARS",
        description="Default retention period in years (configurable per tenant)"
    )
    
    # Async Configuration
    audit_queue_size: int = Field(
        default=1000,
        env="AUDIT_QUEUE_SIZE",
        description="Maximum size of async audit log queue"
    )
    
    audit_batch_size: int = Field(
        default=10,
        env="AUDIT_BATCH_SIZE",
        description="Number of log entries to batch before writing"
    )
    
    audit_flush_interval_seconds: int = Field(
        default=5,
        env="AUDIT_FLUSH_INTERVAL_SECONDS",
        description="Interval in seconds to flush batched logs"
    )


def get_audit_config() -> AuditConfig:
    """Get audit configuration instance.
    
    Returns:
        AuditConfig instance.
    """
    return AuditConfig()
