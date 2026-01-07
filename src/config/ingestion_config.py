"""Configuration for ingestion event streaming."""
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionConfig(BaseSettings):
    """Ingestion configuration from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Kafka/Redpanda Configuration
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        env="KAFKA_BOOTSTRAP_SERVERS",
        description="Kafka/Redpanda bootstrap servers (comma-separated)"
    )
    
    ingestion_topic: str = Field(
        default="ingestion-events",
        env="INGESTION_TOPIC",
        description="Kafka topic name for ingestion events"
    )
    
    # Schema Registry Configuration
    schema_registry_url: Optional[str] = Field(
        default=None,
        env="SCHEMA_REGISTRY_URL",
        description="Schema registry URL (e.g., http://localhost:8081). If not set, uses local validation only."
    )
    
    schema_registry_subject: str = Field(
        default="ingestion-events-value",
        env="SCHEMA_REGISTRY_SUBJECT",
        description="Schema registry subject name for ingestion events"
    )
    
    # Producer Configuration
    kafka_producer_acks: str = Field(
        default="all",
        env="KAFKA_PRODUCER_ACKS",
        description="Kafka producer acks setting (0, 1, or all)"
    )
    
    kafka_producer_retries: int = Field(
        default=3,
        env="KAFKA_PRODUCER_RETRIES",
        description="Number of retries for failed Kafka producer sends"
    )


def get_ingestion_config() -> IngestionConfig:
    """Get ingestion configuration instance."""
    return IngestionConfig()
