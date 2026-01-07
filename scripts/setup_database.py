"""Script to create and verify the control_plane database."""
import os
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("[ERROR] psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)


def get_postgres_connection(database: str = "postgres") -> psycopg2.extensions.connection:
    """Get a connection to PostgreSQL."""
    # Try to get connection details from DATABASE_URL or environment
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        # Parse DATABASE_URL: postgresql://user:password@host:port/database
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        user = parsed.username or "postgres"
        password = parsed.password or ""
        dbname = database
    else:
        # Use individual environment variables
        host = os.getenv("PGHOST", "localhost")
        port = int(os.getenv("PGPORT", "5432"))
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "")
        dbname = database
    
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=dbname
        )
        return conn
    except psycopg2.Error as e:
        print(f"[ERROR] Failed to connect to PostgreSQL: {e}")
        print("\nConnection details:")
        print(f"  Host: {host}")
        print(f"  Port: {port}")
        print(f"  User: {user}")
        print(f"  Database: {dbname}")
        print("\nMake sure:")
        print("  1. PostgreSQL is running")
        print("  2. Connection credentials are correct")
        print("  3. DATABASE_URL is set or PGHOST/PGUSER/PGPASSWORD are set")
        sys.exit(1)


def database_exists(conn: psycopg2.extensions.connection, dbname: str) -> bool:
    """Check if a database exists."""
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s",
        (dbname,)
    )
    
    exists = cursor.fetchone() is not None
    cursor.close()
    return exists


def create_database(dbname: str = "control_plane") -> None:
    """Create the control_plane database if it doesn't exist."""
    print("=" * 60)
    print("Control Plane Database Setup")
    print("=" * 60)
    print()
    
    # Connect to postgres database to create new database
    print("[INFO] Connecting to PostgreSQL...")
    try:
        conn = get_postgres_connection("postgres")
        print("[SUCCESS] Connected to PostgreSQL")
    except SystemExit:
        return
    
    # Check if database exists
    print(f"\n[INFO] Checking if database '{dbname}' exists...")
    if database_exists(conn, dbname):
        print(f"[INFO] Database '{dbname}' already exists")
        conn.close()
        return
    
    # Create database
    print(f"\n[INFO] Creating database '{dbname}'...")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(dbname)
        ))
        print(f"[SUCCESS] Database '{dbname}' created successfully")
    except psycopg2.Error as e:
        print(f"[ERROR] Failed to create database: {e}")
        cursor.close()
        conn.close()
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()
    
    # Verify database was created
    print(f"\n[INFO] Verifying database '{dbname}'...")
    try:
        verify_conn = get_postgres_connection(dbname)
        print(f"[SUCCESS] Successfully connected to database '{dbname}'")
        verify_conn.close()
    except SystemExit:
        return
    
    print("\n" + "=" * 60)
    print("[SUCCESS] Database Setup Complete")
    print("=" * 60)
    print(f"\nDatabase '{dbname}' is ready.")
    print("\nNext steps:")
    print("  1. Set DATABASE_URL environment variable:")
    print(f"     $env:DATABASE_URL=\"postgresql://user:password@localhost:5432/{dbname}\"")
    print("  2. Run migrations:")
    print("     alembic upgrade head")
    print()


def verify_database(dbname: str = "control_plane") -> None:
    """Verify the database exists and is accessible."""
    print("=" * 60)
    print("Database Verification")
    print("=" * 60)
    print()
    
    print(f"[INFO] Checking database '{dbname}'...")
    
    try:
        conn = get_postgres_connection(dbname)
        cursor = conn.cursor()
        
        # Check PostgreSQL version
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"[SUCCESS] Connected to PostgreSQL")
        print(f"  Version: {version.split(',')[0]}")
        
        # Check if control_plane schema exists
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata 
                WHERE schema_name = 'control_plane'
            )
        """)
        schema_exists = cursor.fetchone()[0]
        
        if schema_exists:
            print(f"[SUCCESS] Schema 'control_plane' exists")
            
            # Check tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'control_plane'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            if tables:
                print(f"[SUCCESS] Found {len(tables)} table(s):")
                for table in tables:
                    print(f"  - {table}")
            else:
                print("[INFO] No tables found in control_plane schema")
                print("  Run migrations: alembic upgrade head")
        else:
            print("[INFO] Schema 'control_plane' does not exist yet")
            print("  Run migrations: alembic upgrade head")
        
        cursor.close()
        conn.close()
        
    except SystemExit:
        return
    except psycopg2.Error as e:
        print(f"[ERROR] Database verification failed: {e}")
        sys.exit(1)
    
    print()


def main() -> None:
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Setup control_plane database")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify database exists instead of creating it"
    )
    parser.add_argument(
        "--database",
        default="control_plane",
        help="Database name (default: control_plane)"
    )
    
    args = parser.parse_args()
    
    if args.verify:
        verify_database(args.database)
    else:
        create_database(args.database)


if __name__ == "__main__":
    main()
