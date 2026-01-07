"""Database management for tenant database creation and deletion."""
import os
import logging
from typing import Optional, Tuple
from contextlib import contextmanager

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from src.db.connection import get_connection_manager

logger = logging.getLogger(__name__)


class TenantDatabaseManager:
    """Manages creation and deletion of tenant databases."""
    
    def __init__(self, admin_connection_string: Optional[str] = None):
        """Initialize tenant database manager.
        
        Args:
            admin_connection_string: PostgreSQL connection string with admin privileges.
                                   If not provided, uses DATABASE_URL from environment.
                                   Must connect to 'postgres' database for CREATE DATABASE.
        """
        self.admin_connection_string = admin_connection_string or os.getenv("DATABASE_URL")
        
        if not self.admin_connection_string:
            raise ValueError(
                "DATABASE_URL environment variable is required for tenant database management"
            )
        
        # Ensure we connect to 'postgres' database for admin operations
        self._ensure_admin_connection()
    
    def _ensure_admin_connection(self) -> None:
        """Ensure connection string points to 'postgres' database for admin operations."""
        # Parse connection string and ensure it connects to 'postgres' database
        if "/postgres" not in self.admin_connection_string:
            # Replace database name with 'postgres'
            if "/" in self.admin_connection_string:
                parts = self.admin_connection_string.rsplit("/", 1)
                self.admin_connection_string = f"{parts[0]}/postgres"
            else:
                self.admin_connection_string = f"{self.admin_connection_string}/postgres"
    
    @contextmanager
    def _get_admin_connection(self):
        """Get admin database connection with autocommit for DDL operations."""
        conn = None
        try:
            conn = psycopg2.connect(self.admin_connection_string)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def create_database(self, database_name: str, owner: Optional[str] = None) -> bool:
        """Create a new PostgreSQL database.
        
        Args:
            database_name: Name of the database to create.
            owner: Database owner (optional, uses connection user if not provided).
        
        Returns:
            True if database was created successfully, False if it already exists.
        
        Raises:
            psycopg2.Error: If database creation fails.
        """
        if not database_name:
            raise ValueError("Database name cannot be empty")
        
        # Sanitize database name (PostgreSQL identifier)
        safe_name = database_name.lower().replace("-", "_")
        
        try:
            with self._get_admin_connection() as conn:
                cursor = conn.cursor()
                
                # Check if database already exists
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (safe_name,)
                )
                if cursor.fetchone():
                    logger.warning(f"Database '{safe_name}' already exists")
                    return False
                
                # Create database
                create_query = sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(safe_name)
                )
                
                if owner:
                    create_query = sql.SQL("CREATE DATABASE {} WITH OWNER = {}").format(
                        sql.Identifier(safe_name),
                        sql.Identifier(owner)
                    )
                
                cursor.execute(create_query)
                logger.info(f"Database '{safe_name}' created successfully")
                return True
        
        except psycopg2.Error as e:
            logger.error(f"Failed to create database '{safe_name}': {e}")
            raise
    
    def delete_database(self, database_name: str) -> bool:
        """Delete a PostgreSQL database.
        
        Args:
            database_name: Name of the database to delete.
        
        Returns:
            True if database was deleted successfully, False if it doesn't exist.
        
        Raises:
            psycopg2.Error: If database deletion fails.
        """
        if not database_name:
            raise ValueError("Database name cannot be empty")
        
        safe_name = database_name.lower().replace("-", "_")
        
        try:
            with self._get_admin_connection() as conn:
                cursor = conn.cursor()
                
                # Check if database exists
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (safe_name,)
                )
                if not cursor.fetchone():
                    logger.warning(f"Database '{safe_name}' does not exist")
                    return False
                
                # Terminate all connections to the database
                cursor.execute(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = %s AND pid <> pg_backend_pid()
                    """,
                    (safe_name,)
                )
                
                # Drop database
                drop_query = sql.SQL("DROP DATABASE IF EXISTS {}").format(
                    sql.Identifier(safe_name)
                )
                cursor.execute(drop_query)
                logger.info(f"Database '{safe_name}' deleted successfully")
                return True
        
        except psycopg2.Error as e:
            logger.error(f"Failed to delete database '{safe_name}': {e}")
            raise
    
    def database_exists(self, database_name: str) -> bool:
        """Check if a database exists.
        
        Args:
            database_name: Name of the database to check.
        
        Returns:
            True if database exists, False otherwise.
        """
        safe_name = database_name.lower().replace("-", "_")
        
        try:
            with self._get_admin_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (safe_name,)
                )
                return cursor.fetchone() is not None
        except psycopg2.Error as e:
            logger.error(f"Failed to check database existence: {e}")
            return False
    
    def test_connection(self, connection_string: str) -> Tuple[bool, Optional[str]]:
        """Test database connection.
        
        Args:
            connection_string: PostgreSQL connection string to test.
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str]).
        """
        try:
            conn = psycopg2.connect(connection_string)
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            cursor.fetchone()
            cursor.close()
            conn.close()
            return True, None
        except Exception as e:
            return False, str(e)


def get_tenant_database_manager() -> TenantDatabaseManager:
    """Get or create tenant database manager instance."""
    return TenantDatabaseManager()
