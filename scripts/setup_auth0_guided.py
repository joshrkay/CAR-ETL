"""Guided Auth0 setup script with step-by-step instructions."""
import sys
import os
from typing import Optional
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_header(text: str) -> None:
    """Print formatted header."""
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def check_env_var(name: str, value: Optional[str]) -> bool:
    """Check if environment variable is set."""
    if value:
        print(f"  [OK] {name} = {value[:20]}..." if len(value) > 20 else f"  [OK] {name} = {value}")
        return True
    else:
        print(f"  [MISSING] {name}")
        return False


def main() -> None:
    """Guided setup main function."""
    print_header("Auth0 Setup Guide for CAR Platform")
    
    # Known domain from certificate
    known_domain = "dev-khx88c3lu7wz2dxx.us.auth0.com"
    
    print("\nStep 1: Environment Variables Check")
    print("-" * 60)
    
    domain = os.getenv("AUTH0_DOMAIN")
    client_id = os.getenv("AUTH0_MANAGEMENT_CLIENT_ID")
    client_secret = os.getenv("AUTH0_MANAGEMENT_CLIENT_SECRET")
    db_connection = os.getenv("AUTH0_DATABASE_CONNECTION_NAME", "Username-Password-Authentication")
    api_identifier = os.getenv("AUTH0_API_IDENTIFIER", "https://api.car-platform.com")
    
    has_domain = check_env_var("AUTH0_DOMAIN", domain)
    has_client_id = check_env_var("AUTH0_MANAGEMENT_CLIENT_ID", client_id)
    has_client_secret = check_env_var("AUTH0_MANAGEMENT_CLIENT_SECRET", client_secret)
    check_env_var("AUTH0_DATABASE_CONNECTION_NAME", db_connection)
    check_env_var("AUTH0_API_IDENTIFIER", api_identifier)
    
    print("\nStep 2: Quick Setup")
    print("-" * 60)
    
    if not has_domain:
        print(f"\nSet AUTH0_DOMAIN (from your certificate):")
        print(f"  PowerShell: $env:AUTH0_DOMAIN=\"{known_domain}\"")
        print(f"  CMD: set AUTH0_DOMAIN={known_domain}")
        print(f"  Or add to .env file: AUTH0_DOMAIN={known_domain}")
    
    if not has_client_id or not has_client_secret:
        print("\n" + "=" * 60)
        print("CREATE MANAGEMENT API CLIENT")
        print("=" * 60)
        print("\n1. Go to: https://manage.auth0.com")
        print("2. Navigate to: Applications > Applications")
        print("3. Click: '+ Create Application'")
        print("4. Name: 'CAR Platform Management Client'")
        print("5. Type: 'Machine to Machine Applications'")
        print("6. Click: 'Create'")
        print("7. In 'APIs' tab, select: 'Auth0 Management API'")
        print("8. Toggle: 'Authorize'")
        print("9. Grant these permissions:")
        print("   [X] read:users")
        print("   [X] create:users")
        print("   [X] update:users")
        print("   [X] delete:users")
        print("   [X] read:connections")
        print("   [X] update:connections")
        print("   [X] read:resource_servers")
        print("   [X] create:resource_servers")
        print("   [X] update:resource_servers")
        print("10. Click: 'Authorize'")
        print("11. Go to 'Settings' tab")
        print("12. Copy 'Client ID' and 'Client Secret'")
        print("\nThen set environment variables:")
        print("  PowerShell:")
        print("    $env:AUTH0_MANAGEMENT_CLIENT_ID=\"your-client-id\"")
        print("    $env:AUTH0_MANAGEMENT_CLIENT_SECRET=\"your-client-secret\"")
        print("  Or add to .env file")
        print("=" * 60)
    
    if has_domain and has_client_id and has_client_secret:
        print("\n" + "=" * 60)
        print("READY TO RUN SETUP")
        print("=" * 60)
        print("\nAll required environment variables are set!")
        print("Run the setup script:")
        print("  python scripts/setup_auth0.py")
        print("\nThis will:")
        print("  [X] Create API resource 'CAR API'")
        print("  [X] Configure scopes: read:documents, write:documents, admin")
        print("  [X] Set JWT signing to RS256")
        print("  [X] Configure database connection password policy")
    else:
        print("\n" + "=" * 60)
        print("NEXT STEPS")
        print("=" * 60)
        print("\n1. Set the missing environment variables (see above)")
        print("2. Run this script again to verify")
        print("3. Then run: python scripts/setup_auth0.py")
    
    print("\n" + "=" * 60)
    print("MANUAL API RESOURCE CREATION (Alternative)")
    print("=" * 60)
    print("\nIf you prefer to create the API resource manually:")
    print("\n1. Go to: https://manage.auth0.com")
    print("2. Navigate to: APIs > APIs")
    print("3. Click: '+ Create API'")
    print("4. Name: 'CAR API'")
    print("5. Identifier: 'https://api.car-platform.com'")
    print("6. Signing Algorithm: 'RS256'")
    print("7. Click: 'Create'")
    print("8. Go to 'Scopes' tab")
    print("9. Add scopes:")
    print("   - read:documents (Read document data)")
    print("   - write:documents (Create/update documents)")
    print("   - admin (Administrative operations)")
    print("10. Save changes")
    print("=" * 60)
    
    print("\n" + "=" * 60)
    print("DATABASE CONNECTION PASSWORD POLICY")
    print("=" * 60)
    print("\n1. Go to: Authentication > Database > Database Connections")
    print("2. Click on: 'Username-Password-Authentication' (or your connection)")
    print("3. Go to 'Settings' tab")
    print("4. Scroll to 'Password Policy'")
    print("5. Set:")
    print("   - Password Policy: 'Fair' or 'Good'")
    print("   - Minimum Length: 8")
    print("   - Require Lowercase: [X]")
    print("   - Require Numbers: [X]")
    print("   - Require Symbols: [X]")
    print("6. Save changes")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
