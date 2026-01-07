"""Script to help create CAR API resource in Auth0."""
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.auth.config import get_auth0_config


def print_instructions() -> None:
    """Print step-by-step instructions for creating API resource."""
    try:
        config = get_auth0_config()
        domain = config.domain
        api_identifier = config.api_identifier
    except:
        domain = "dev-khx88c3lu7wz2dxx.us.auth0.com"
        api_identifier = "https://api.car-platform.com"
    
    print("=" * 70)
    print("Create CAR API Resource in Auth0 Dashboard")
    print("=" * 70)
    print()
    print("Since Management API is not enabled, create the API resource manually.")
    print()
    
    print("STEP 1: Navigate to Auth0 Dashboard")
    print("-" * 70)
    print("1. Go to: https://manage.auth0.com")
    print("2. Make sure you're logged in to the correct tenant")
    print(f"3. Your tenant domain: {domain}")
    print()
    
    print("STEP 2: Create API Resource")
    print("-" * 70)
    print("1. In the left sidebar, click on 'APIs'")
    print("2. Click on 'APIs' (not 'Machine to Machine Applications')")
    print("3. Click the '+ Create API' button (top right)")
    print()
    print("STEP 3: Fill in API Details")
    print("-" * 70)
    print("In the 'Create API' form, enter:")
    print()
    print("  Name:")
    print("    CAR API")
    print()
    print("  Identifier:")
    print(f"    {api_identifier}")
    print("    (IMPORTANT: Must match exactly, including https://)")
    print()
    print("  Signing Algorithm:")
    print("    RS256")
    print("    (Select from dropdown)")
    print()
    print("4. Click 'Create' button")
    print()
    
    print("STEP 4: Configure API Scopes")
    print("-" * 70)
    print("After creating the API, you'll be on the API settings page.")
    print()
    print("1. Click on the 'Scopes' tab")
    print("2. Add the following scopes (click 'Add' for each):")
    print()
    print("   Scope 1:")
    print("     Name: read:documents")
    print("     Description: Read document data")
    print()
    print("   Scope 2:")
    print("     Name: write:documents")
    print("     Description: Create/update documents")
    print()
    print("   Scope 3:")
    print("     Name: admin")
    print("     Description: Administrative operations")
    print()
    print("3. Click 'Add' for each scope")
    print("4. Verify all three scopes are listed")
    print()
    
    print("STEP 5: Verify API Configuration")
    print("-" * 70)
    print("1. Go to the 'Settings' tab")
    print("2. Verify:")
    print(f"   - Identifier: {api_identifier}")
    print("   - Signing Algorithm: RS256")
    print("3. Note the API ID (you may need it later)")
    print()
    
    print("STEP 6: Authorize Your Client")
    print("-" * 70)
    print("Now authorize your client application to use this API:")
    print()
    print("1. Go to 'Applications' > 'Applications' in the left sidebar")
    print("2. Find your application:")
    print("   Client ID: bjtGWwmdLFUfpHZRN3FCirQxUeIGDFBq")
    print("   (Or search for it)")
    print()
    print("3. Click on the application to open it")
    print("4. Go to the 'APIs' tab")
    print("5. You should see 'CAR API' in the dropdown list")
    print("6. Select 'CAR API' from the dropdown")
    print("7. Toggle the 'Authorize' switch to ON")
    print()
    print("8. You'll see a list of scopes - check these:")
    print("   [X] read:documents")
    print("   [X] write:documents")
    print("   [X] admin")
    print()
    print("9. Click 'Update' or 'Authorize' button")
    print()
    
    print("STEP 7: Test the Configuration")
    print("-" * 70)
    print("After completing the above steps, run:")
    print()
    print("  python scripts/test_jwt_new_client.py")
    print()
    print("You should see:")
    print("  [SUCCESS] Token obtained")
    print("  [SUCCESS] Token verified successfully")
    print()
    
    print("=" * 70)
    print("Quick Reference")
    print("=" * 70)
    print()
    print("API Resource Details:")
    print(f"  Name: CAR API")
    print(f"  Identifier: {api_identifier}")
    print(f"  Algorithm: RS256")
    print()
    print("Scopes:")
    print("  - read:documents")
    print("  - write:documents")
    print("  - admin")
    print()
    print("Client to Authorize:")
    print("  Client ID: bjtGWwmdLFUfpHZRN3FCirQxUeIGDFBq")
    print()
    print("=" * 70)


def main() -> None:
    """Main function."""
    print_instructions()
    
    print("\n[INFO] After creating the API resource, you can verify it with:")
    print("  python scripts/verify_api_resource.py")
    print()


if __name__ == "__main__":
    main()
