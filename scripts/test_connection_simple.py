"""Simple connection test for Supabase."""
import os
import sys
from urllib.parse import urlparse

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("[ERROR] psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)

def test_connection():
    """Test database connection with various formats."""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("[ERROR] DATABASE_URL environment variable not set")
        print("\nSet it with:")
        print('  $env:DATABASE_URL="postgresql://postgres:[PASSWORD]@db.qifioafprrtkoiyylsqa.supabase.co:5432/postgres?sslmode=require"')
        sys.exit(1)
    
    print(f"[INFO] Testing connection with DATABASE_URL...")
    print(f"[INFO] Host: {urlparse(database_url).hostname}")
    
    try:
        conn = psycopg2.connect(database_url)
        print("[SUCCESS] Connection established!")
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"[INFO] PostgreSQL version: {version[:50]}...")
        
        cursor.execute("SELECT current_database();")
        db_name = cursor.fetchone()[0]
        print(f"[INFO] Connected to database: {db_name}")
        
        cursor.close()
        conn.close()
        print("[SUCCESS] Connection test passed!")
        return True
        
    except psycopg2.OperationalError as e:
        print(f"[ERROR] Connection failed: {e}")
        print("\n[TROUBLESHOOTING]")
        print("1. Verify your password is correct")
        print("2. Check if your IP is whitelisted in Supabase (Settings > Database > Connection Pooling)")
        print("3. Try using the exact connection string from Supabase dashboard:")
        print("   https://app.supabase.com/project/qifioafprrtkoiyylsqa/settings/database")
        print("4. If connection still fails, use the manual SQL migration:")
        print("   See: docs/MANUAL_MIGRATION_INSTRUCTIONS.md")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
