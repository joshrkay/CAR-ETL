"""Test connection using IP address directly (workaround for DNS issues)."""
import os
import sys
import socket

try:
    import psycopg2
except ImportError:
    print("[ERROR] psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)

def resolve_hostname(hostname: str) -> str:
    """Resolve hostname to IP address."""
    try:
        ip = socket.gethostbyname(hostname)
        print(f"[INFO] Resolved {hostname} to {ip}")
        return ip
    except socket.gaierror as e:
        print(f"[ERROR] Could not resolve {hostname}: {e}")
        return None

def test_connection_with_ip():
    """Test connection using IP address instead of hostname."""
    hostname = "db.qifioafprrtkoiyylsqa.supabase.co"
    password = "4VNTmrNhb3NyoI2r"
    
    # Try to resolve IP
    ip = resolve_hostname(hostname)
    if not ip:
        print("[ERROR] Cannot resolve hostname. DNS issue persists.")
        print("\n[SOLUTION] Run the migration manually in Supabase SQL Editor:")
        print("  1. Go to: https://app.supabase.com/project/qifioafprrtkoiyylsqa")
        print("  2. Open SQL Editor")
        print("  3. Run: scripts/run_migrations_manually.sql")
        return False
    
    # Try connection with IP
    ip_url = f"postgresql://postgres:{password}@{ip}:5432/postgres?sslmode=require"
    
    print(f"\n[INFO] Trying connection with IP address: {ip}")
    
    try:
        # Note: PostgreSQL might reject connections by IP if hostname verification is required
        # But it's worth trying
        conn = psycopg2.connect(ip_url)
        print("[SUCCESS] Connection with IP established!")
        
        cursor = conn.cursor()
        cursor.execute("SELECT current_database();")
        db_name = cursor.fetchone()[0]
        print(f"[INFO] Connected to database: {db_name}")
        
        cursor.close()
        conn.close()
        print("\n[SUCCESS] IP connection works!")
        print(f"\n[INFO] You can use this connection string (temporary workaround):")
        print(f'  $env:DATABASE_URL="postgresql://postgres:{password}@{ip}:5432/postgres?sslmode=require"')
        return True
        
    except psycopg2.OperationalError as e:
        print(f"[ERROR] IP connection failed: {e}")
        print("\n[NOTE] PostgreSQL may require hostname for SSL verification.")
        print("[SOLUTION] Run the migration manually in Supabase SQL Editor.")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_connection_with_ip()
    sys.exit(0 if success else 1)
