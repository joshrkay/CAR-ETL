"""Test Supabase connection with different hostname formats."""
import os
import sys

try:
    import psycopg2
except ImportError:
    print("[ERROR] psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)


def test_connection(hostname: str, password: str, project_ref: str) -> bool:
    """Test connection to Supabase."""
    connection_strings = [
        # Format 1: Direct connection
        f"postgresql://postgres:{password}@db.{project_ref}.supabase.co:5432/postgres?sslmode=require",
        # Format 2: Pooler connection
        f"postgresql://postgres.{project_ref}:{password}@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require",
        # Format 3: Alternative pooler
        f"postgresql://postgres.{project_ref}:{password}@aws-0-us-west-1.pooler.supabase.com:6543/postgres?sslmode=require",
        # Format 4: Custom hostname
        f"postgresql://postgres:{password}@{hostname}:5432/postgres?sslmode=require",
    ]
    
    print("=" * 70)
    print("Testing Supabase Connection Formats")
    print("=" * 70)
    print()
    print(f"Project Reference: {project_ref}")
    print(f"Password: {'*' * len(password)}")
    print()
    
    for i, conn_str in enumerate(connection_strings, 1):
        print(f"Test {i}: Trying connection format...")
        try:
            conn = psycopg2.connect(conn_str)
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            print(f"[SUCCESS] Connection {i} works!")
            print(f"  Connection string: {conn_str.split('@')[0]}@***")
            print(f"  PostgreSQL version: {version.split(',')[0]}")
            print()
            print("=" * 70)
            print("[SUCCESS] Use this connection string:")
            print("=" * 70)
            print(conn_str)
            print()
            return True
        except psycopg2.OperationalError as e:
            error_msg = str(e)
            if "could not translate host name" in error_msg:
                print(f"  [FAILED] DNS resolution error")
            elif "password authentication failed" in error_msg:
                print(f"  [FAILED] Authentication failed (wrong password)")
            elif "connection refused" in error_msg:
                print(f"  [FAILED] Connection refused (wrong port/host)")
            else:
                print(f"  [FAILED] {error_msg[:100]}")
        except Exception as e:
            print(f"  [FAILED] {str(e)[:100]}")
        print()
    
    print("=" * 70)
    print("[ERROR] None of the connection formats worked")
    print("=" * 70)
    print()
    print("Please verify:")
    print("  1. Project reference is correct: qifioafprrtkoiyylsqa")
    print("  2. Password is correct")
    print("  3. Get the exact connection string from Supabase Dashboard:")
    print("     - Go to https://app.supabase.com")
    print("     - Settings > Database > Connection string > URI")
    print()
    return False


def main() -> None:
    """Main function."""
    password = "4VNTmrNhb3NyoI2r"
    project_ref = "qifioafprrtkoiyylsqa"
    
    # Try the provided hostname first
    hostname = f"db.{project_ref}.supabase.co"
    
    success = test_connection(hostname, password, project_ref)
    
    if not success:
        print("\nAlternative: Get connection string from Supabase Dashboard")
        print("1. Go to: https://app.supabase.com")
        print("2. Select your project")
        print("3. Settings > Database")
        print("4. Connection string > URI tab")
        print("5. Copy the exact connection string")
        print("6. Set it as DATABASE_URL")


if __name__ == "__main__":
    main()
