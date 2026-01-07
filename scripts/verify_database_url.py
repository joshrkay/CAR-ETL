"""Verify DATABASE_URL is set correctly."""
import os
import sys
from urllib.parse import urlparse

def verify_database_url() -> None:
    """Verify DATABASE_URL environment variable."""
    print("=" * 60)
    print("DATABASE_URL Verification")
    print("=" * 60)
    print()
    
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("[ERROR] DATABASE_URL environment variable is not set")
        print()
        print("Set it with:")
        print('  PowerShell: $env:DATABASE_URL="postgresql://user:password@host:port/database"')
        print('  CMD: set DATABASE_URL=postgresql://user:password@host:port/database')
        print('  Or add to .env file: DATABASE_URL=postgresql://user:password@host:port/database')
        sys.exit(1)
    
    print(f"[SUCCESS] DATABASE_URL is set")
    print(f"  Value: {database_url}")
    print()
    
    # Parse and validate URL
    try:
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        
        print("[INFO] Parsed connection details:")
        print(f"  Scheme: {parsed.scheme}")
        print(f"  Host: {parsed.hostname or 'localhost'}")
        print(f"  Port: {parsed.port or 5432}")
        print(f"  User: {parsed.username or 'postgres'}")
        print(f"  Database: {parsed.path.lstrip('/') if parsed.path else 'postgres'}")
        print(f"  Password: {'***' if parsed.password else '(not set)'}")
        print()
        
        if parsed.scheme not in ["postgresql", "postgres"]:
            print("[WARN] Scheme should be 'postgresql' or 'postgres'")
        
        if not parsed.path or parsed.path == "/":
            print("[WARN] Database name not specified in URL")
        
        if not parsed.username:
            print("[WARN] Username not specified in URL")
        
    except Exception as e:
        print(f"[ERROR] Failed to parse DATABASE_URL: {e}")
        sys.exit(1)
    
    # Test connection (optional)
    print("[INFO] Testing database connection...")
    try:
        import psycopg2
        from urllib.parse import urlparse, urlunparse
        
        # psycopg2 expects postgresql:// not postgres://
        if parsed.scheme == "postgres":
            db_url = urlunparse(("postgresql",) + parsed[1:])
        else:
            db_url = database_url
        
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"[SUCCESS] Connected to PostgreSQL")
        print(f"  Version: {version.split(',')[0]}")
        
        # Check if control_plane database exists
        cursor.execute("SELECT current_database()")
        current_db = cursor.fetchone()[0]
        print(f"  Current database: {current_db}")
        
        cursor.close()
        conn.close()
        
    except ImportError:
        print("[INFO] psycopg2 not available - skipping connection test")
        print("  Install with: pip install psycopg2-binary")
    except Exception as e:
        print(f"[WARN] Connection test failed: {e}")
        print("  This is okay if the database doesn't exist yet")
        print("  Create it first, then run migrations")
    
    print()
    print("=" * 60)
    print("[SUCCESS] DATABASE_URL is configured")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Create the database (if not exists):")
    print("     python scripts/setup_database.py")
    print("  2. Run migrations:")
    print("     alembic upgrade head")


if __name__ == "__main__":
    verify_database_url()
