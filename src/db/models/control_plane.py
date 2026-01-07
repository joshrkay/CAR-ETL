"""Control plane database models for CAR Platform."""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Integer, Text, JSON, Boolean,
    Index, Enum as SQLEnum, event
)
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class TenantEnvironment(PyEnum):
    """Tenant environment types."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class TenantStatus(PyEnum):
    """Tenant status types."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class DatabaseStatus(PyEnum):
    """Database connection status types."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    MIGRATING = "migrating"
    ERROR = "error"


class Tenant(Base):
    """Tenant model for multi-tenant architecture."""

    __tablename__ = "tenants"
    __table_args__ = (
        Index("idx_tenants_status", "status"),
        {"schema": "control_plane"}
    )

    tenant_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    name = Column(String(255), nullable=False, unique=True)
    environment = Column(
        SQLEnum(TenantEnvironment, name="tenant_environment", schema="control_plane"),
        nullable=False
    )
    status = Column(
        SQLEnum(TenantStatus, name="tenant_status", schema="control_plane"),
        nullable=False,
        default=TenantStatus.PENDING
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    databases = relationship("TenantDatabase", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<Tenant(tenant_id={self.tenant_id}, "
            f"name={self.name}, "
            f"environment={self.environment.value}, "
            f"status={self.status.value})>"
        )


class TenantDatabase(Base):
    """Tenant database connection information."""

    __tablename__ = "tenant_databases"
    __table_args__ = (
        Index("idx_tenant_databases_tenant_id", "tenant_id"),
        Index("idx_tenant_databases_status", "status"),
        {"schema": "control_plane"}
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("control_plane.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False
    )
    connection_string_encrypted = Column(Text, nullable=False)
    database_name = Column(String(255), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False, default=5432)
    status = Column(
        SQLEnum(DatabaseStatus, name="database_status", schema="control_plane"),
        nullable=False,
        default=DatabaseStatus.INACTIVE
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="databases")

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<TenantDatabase(id={self.id}, "
            f"tenant_id={self.tenant_id}, "
            f"database_name={self.database_name}, "
            f"host={self.host}, "
            f"status={self.status.value})>"
        )


class SystemConfig(Base):
    """System-wide configuration key-value store."""

    __tablename__ = "system_config"
    __table_args__ = {"schema": "control_plane"}

    key = Column(String(255), primary_key=True, nullable=False)
    value = Column(JSONB, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<SystemConfig(key={self.key}, value={self.value})>"


class ServiceAccountToken(Base):
    """Service account API token model."""

    __tablename__ = "service_account_tokens"
    __table_args__ = (
        Index("idx_service_account_tokens_tenant_id", "tenant_id"),
        Index("idx_service_account_tokens_token_hash", "token_hash"),
        Index("idx_service_account_tokens_is_revoked", "is_revoked"),
        Index("idx_service_account_tokens_created_at", "created_at"),
        {"schema": "control_plane"}
    )

    token_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("control_plane.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False
    )
    token_hash = Column(String(255), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    is_revoked = Column(sa.Boolean(), nullable=False, default=False)

    # Relationships
    tenant = relationship("Tenant")

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<ServiceAccountToken(token_id={self.token_id}, "
            f"tenant_id={self.tenant_id}, "
            f"name={self.name}, "
            f"role={self.role}, "
            f"is_revoked={self.is_revoked})>"
        )


# Event listeners for auto-updating updated_at
@event.listens_for(Tenant, "before_update", propagate=True)
def receive_before_update_tenant(mapper, connection, target):
    """Update updated_at timestamp before update."""
    target.updated_at = datetime.utcnow()


@event.listens_for(TenantDatabase, "before_update", propagate=True)
def receive_before_update_database(mapper, connection, target):
    """Update updated_at timestamp before update."""
    target.updated_at = datetime.utcnow()


@event.listens_for(SystemConfig, "before_update", propagate=True)
def receive_before_update_config(mapper, connection, target):
    """Update updated_at timestamp before update."""
    target.updated_at = datetime.utcnow()
