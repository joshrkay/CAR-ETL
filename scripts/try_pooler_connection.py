"""Try connecting via Supabase pooler (alternative connection method)."""
import os
import sys

try:
    import psycopg2
except ImportError:
    print("[ERROR] psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)

def try_pooler_connection():
    """Try connecting via Supabase pooler connection string."""
    # Supabase pooler uses port 6543 and different hostname format
    project_ref = "qifioafprrtkoiyylsqa"
    password = "4VNTmrNhb3NyoI2r"
    
    # Try pooler connection (port 6543, session mode)
    pooler_url = f"postgresql://postgres.{project_ref}:{password}@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
    
    print("[INFO] Trying Supabase pooler connection...")
    print(f"[INFO] Host: aws-0-us-east-1.pooler.supabase.com:6543")
    
    try:
        conn = psycopg2.connect(pooler_url)
        print("[SUCCESS] Pooler connection established!")
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"[INFO] PostgreSQL version: {version[:50]}...")
        
        cursor.execute("SELECT current_database();")
        db_name = cursor.fetchone()[0]
        print(f"[INFO] Connected to database: {db_name}")
        
        cursor.close()
        conn.close()
        print("\n[SUCCESS] Pooler connection works!")
        print("\n[INFO] Update your DATABASE_URL to use the pooler:")
        print(f'  $env:DATABASE_URL="{pooler_url}"')
        return True
        
    except psycopg2.OperationalError as e:
        print(f"[ERROR] Pooler connection failed: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = try_pooler_connection()
    sys.exit(0 if success else 1)
