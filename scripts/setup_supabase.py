"""Setup script for Supabase database connection."""
import os
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_supabase_setup() -> None:
    """Print Supabase setup instructions."""
    print("=" * 70)
    print("Supabase Database Setup for CAR Platform")
    print("=" * 70)
    print()
    
    print("STEP 1: Get Your Supabase Connection String")
    print("-" * 70)
    print("1. Go to: https://app.supabase.com")
    print("2. Sign in and select your project")
    print("3. Navigate to: Settings > Database")
    print("4. Scroll to 'Connection string' section")
    print("5. Select 'URI' tab")
    print("6. Copy the connection string")
    print()
    print("Connection string format:")
    print("  postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres")
    print()
    
    print("STEP 2: Update Connection String for Migrations")
    print("-" * 70)
    print("For migrations, use Session Mode (port 5432) with SSL:")
    print()
    print("  postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres?sslmode=require")
    print()
    print("Replace:")
    print("  [PASSWORD] - Your Supabase database password")
    print("  [PROJECT-REF] - Your Supabase project reference ID")
    print()
    
    print("STEP 3: Set DATABASE_URL Environment Variable")
    print("-" * 70)
    print("PowerShell:")
    print('  $env:DATABASE_URL="postgresql://postgres:password@db.project.supabase.co:5432/postgres?sslmode=require"')
    print()
    print("Or create a .env file:")
    print('  DATABASE_URL=postgresql://postgres:password@db.project.supabase.co:5432/postgres?sslmode=require')
    print()
    
    # Check if DATABASE_URL is already set
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        print("STEP 4: Current DATABASE_URL")
        print("-" * 70)
        print(f"Current value: {database_url}")
        
        # Check if it's a Supabase URL
        if "supabase" in database_url.lower():
            print("[SUCCESS] DATABASE_URL appears to be a Supabase connection")
            
            # Check for SSL
            if "sslmode" not in database_url:
                print("[WARN] SSL mode not specified. Add ?sslmode=require for Supabase")
        else:
            print("[INFO] DATABASE_URL doesn't appear to be Supabase")
    else:
        print("STEP 4: DATABASE_URL Not Set")
        print("-" * 70)
        print("[INFO] DATABASE_URL environment variable is not set")
        print("  Set it using the instructions in Step 3")
    
    print()
    print("STEP 5: Verify Connection")
    print("-" * 70)
    print("Run:")
    print("  python scripts/verify_database_url.py")
    print()
    
    print("STEP 6: Run Migrations")
    print("-" * 70)
    print("Once DATABASE_URL is set correctly:")
    print("  python -m alembic upgrade head")
    print()
    
    print("=" * 70)
    print("Supabase-Specific Notes")
    print("=" * 70)
    print()
    print("1. SSL Required: Supabase requires SSL connections")
    print("   Add ?sslmode=require to your connection string")
    print()
    print("2. Use Session Mode for Migrations:")
    print("   Port 5432 (direct connection) for Alembic migrations")
    print("   Port 6543 (pooler) for application connections")
    print()
    print("3. Default Database: Supabase uses 'postgres' database")
    print("   The control_plane schema will be created within it")
    print()
    print("4. Verify in Dashboard:")
    print("   After migrations, check Table Editor in Supabase")
    print("   Look for 'control_plane' schema and tables")
    print()
    print("=" * 70)


if __name__ == "__main__":
    print_supabase_setup()
