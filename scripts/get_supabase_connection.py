"""Helper script to guide getting Supabase connection string."""
import webbrowser
import os

def main() -> None:
    """Open Supabase dashboard and guide user."""
    print("=" * 70)
    print("Get Supabase Database Connection String")
    print("=" * 70)
    print()
    
    project_url = "https://qifioafprrtkoiyylsqa.supabase.co"
    dashboard_url = "https://app.supabase.com/project/qifioafprrtkoiyylsqa/settings/database"
    
    print(f"Your Supabase Project: {project_url}")
    print()
    print("STEP 1: Opening Supabase Dashboard...")
    print()
    
    try:
        webbrowser.open(dashboard_url)
        print(f"[SUCCESS] Opened: {dashboard_url}")
    except Exception as e:
        print(f"[INFO] Could not open browser automatically: {e}")
        print(f"Please open manually: {dashboard_url}")
    
    print()
    print("STEP 2: Get Connection String")
    print("-" * 70)
    print("In the Supabase dashboard:")
    print("1. Scroll down to 'Connection string' section")
    print("2. Click on 'URI' tab")
    print("3. Select 'Session mode' (not Transaction mode)")
    print("4. Copy the connection string")
    print()
    print("The connection string should look like:")
    print("  postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres")
    print("  OR")
    print("  postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres")
    print()
    
    print("STEP 3: Add SSL Parameter")
    print("-" * 70)
    print("Add ?sslmode=require to the end of the connection string:")
    print("  [CONNECTION_STRING]?sslmode=require")
    print()
    print("If it already has parameters, add &sslmode=require:")
    print("  [CONNECTION_STRING]&sslmode=require")
    print()
    
    print("STEP 4: Set DATABASE_URL")
    print("-" * 70)
    print("PowerShell:")
    print('  $env:DATABASE_URL="[PASTE_CONNECTION_STRING_HERE]?sslmode=require"')
    print()
    print("Or create a .env file:")
    print('  DATABASE_URL=[PASTE_CONNECTION_STRING_HERE]?sslmode=require')
    print()
    
    print("STEP 5: Test Connection")
    print("-" * 70)
    print("After setting DATABASE_URL, run:")
    print("  python scripts/verify_database_url.py")
    print()
    
    print("STEP 6: Run Migrations")
    print("-" * 70)
    print("Once connection works:")
    print("  python -m alembic upgrade head")
    print()
    
    print("=" * 70)
    print("Alternative: Try Pooler Connection")
    print("=" * 70)
    print()
    print("If direct connection doesn't work, try the pooler:")
    print('  $env:DATABASE_URL="postgresql://postgres.qifioafprrtkoiyylsqa:4VNTmrNhb3NyoI2r@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"')
    print()
    print("Or try different regions:")
    print("  - aws-0-us-east-1.pooler.supabase.com")
    print("  - aws-0-us-west-1.pooler.supabase.com")
    print("  - aws-0-eu-west-1.pooler.supabase.com")
    print()


if __name__ == "__main__":
    main()
