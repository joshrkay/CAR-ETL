"""Database connection manager for CAR Platform."""
import os
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from .models.control_plane import Base


class DatabaseConnectionManager:
    """Manages database connections for the control plane."""

    def __init__(self, database_url: Optional[str] = None):
        """Initialize database connection manager."""
        self.database_url = database_url or os.getenv("DATABASE_URL")
        
        if not self.database_url:
            raise ValueError(
                "DATABASE_URL environment variable is required. "
                "Format: postgresql://user:password@host:port/database"
            )
        
        # Use NullPool for serverless/connection pooling scenarios
        # For Supabase, ensure SSL is configured
        connect_args = {}
        if "supabase" in self.database_url.lower() and "sslmode" not in self.database_url:
            # Add SSL mode if not present for Supabase connections
            connect_args["sslmode"] = "require"
        
        self.engine = create_engine(
            self.database_url,
            poolclass=NullPool,
            echo=False,
            future=True,
            connect_args=connect_args
        )
        
        # Configure connection settings
        self._configure_connection()
        
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )

    def _configure_connection(self) -> None:
        """Configure database connection settings."""
        
        @event.listens_for(self.engine, "connect")
        def set_search_path(dbapi_conn, connection_record):
            """Set connection-level settings."""
            # Ensure we're using the control_plane schema
            with dbapi_conn.cursor() as cursor:
                cursor.execute("SET search_path TO control_plane, public")

    def create_schema(self) -> None:
        """Create the control_plane schema if it doesn't exist."""
        with self.engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS control_plane"))
            conn.commit()

    def create_tables(self) -> None:
        """Create all tables in the control_plane schema."""
        self.create_schema()
        Base.metadata.create_all(bind=self.engine, schema="control_plane")

    def drop_tables(self) -> None:
        """Drop all tables in the control_plane schema."""
        Base.metadata.drop_all(bind=self.engine, schema="control_plane")

    @contextmanager
    def get_session(self) -> Session:
        """Get a database session with automatic cleanup."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session_direct(self) -> Session:
        """Get a database session (caller must close)."""
        return self.SessionLocal()

    def health_check(self) -> bool:
        """Check if database connection is healthy."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


# Global connection manager instance
_connection_manager: Optional[DatabaseConnectionManager] = None


def get_connection_manager() -> DatabaseConnectionManager:
    """Get or create the global database connection manager."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = DatabaseConnectionManager()
    return _connection_manager


def init_db(database_url: Optional[str] = None) -> DatabaseConnectionManager:
    """Initialize the database connection manager."""
    global _connection_manager
    _connection_manager = DatabaseConnectionManager(database_url)
    return _connection_manager
