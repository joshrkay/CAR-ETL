"""Seed feature flags via admin API for testing."""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()
except ImportError:
    # `python-dotenv` is optional; if it's not installed, continue without loading a .env file.
    sys.stderr.write("Warning: python-dotenv not installed; skipping loading .env file.\n")

from supabase import create_client
from src.auth.config import get_auth_config
from src.features.models import FeatureFlagCreate, TenantFeatureFlagUpdate


def seed_flags():
    """Create seed feature flags for testing."""
    config = get_auth_config()
    
    # Initialize Supabase client with service key (admin access)
    supabase = create_client(
        config.supabase_url,
        config.supabase_service_key,
    )
    
    print("=" * 60)
    print("Seeding Feature Flags")
    print("=" * 60)
    
    # Define seed flags
    seed_flags_data = [
        {
            "name": "experimental_search",
            "description": "New experimental search algorithm with improved relevance",
            "enabled_default": False,
        },
        {
            "name": "advanced_analytics",
            "description": "Advanced analytics dashboard with real-time metrics",
            "enabled_default": True,
        },
        {
            "name": "ai_summarization",
            "description": "AI-powered document summarization feature",
            "enabled_default": False,
        },
        {
            "name": "bulk_export",
            "description": "Bulk export functionality for large datasets",
            "enabled_default": True,
        },
        {
            "name": "dark_mode",
            "description": "Dark mode UI theme",
            "enabled_default": False,
        },
        {
            "name": "api_v2",
            "description": "New API v2 endpoints with improved performance",
            "enabled_default": False,
        },
    ]
    
    created_flags = []
    
    for flag_data in seed_flags_data:
        print(f"\nCreating flag: {flag_data['name']}...")
        try:
            # Check if flag already exists
            existing = (
                supabase.table("feature_flags")
                .select("id, name")
                .eq("name", flag_data["name"])
                .limit(1)
                .execute()
            )
            
            if existing.data:
                flag_id = existing.data[0]["id"]
                print(f"  [SKIP] Flag '{flag_data['name']}' already exists (ID: {flag_id})")
                created_flags.append({
                    "id": flag_id,
                    "name": flag_data["name"],
                    "exists": True,
                })
            else:
                # Create the flag
                result = (
                    supabase.table("feature_flags")
                    .insert({
                        "name": flag_data["name"],
                        "description": flag_data["description"],
                        "enabled_default": flag_data["enabled_default"],
                    })
                    .execute()
                )
                
                if result.data:
                    flag_id = result.data[0]["id"]
                    print(f"  [OK] Created flag '{flag_data['name']}' (ID: {flag_id})")
                    print(f"       Default: {'Enabled' if flag_data['enabled_default'] else 'Disabled'}")
                    created_flags.append({
                        "id": flag_id,
                        "name": flag_data["name"],
                        "exists": False,
                    })
                else:
                    print(f"  [ERROR] Failed to create flag '{flag_data['name']}'")
                    
        except Exception as e:
            print(f"  [ERROR] Failed to create flag '{flag_data['name']}': {e}")
    
    print("\n" + "=" * 60)
    print(f"Created/Found {len(created_flags)} feature flags")
    print("=" * 60)
    
    # List all flags
    print("\nAll Feature Flags:")
    try:
        all_flags = (
            supabase.table("feature_flags")
            .select("*")
            .order("name")
            .execute()
        )
        
        if all_flags.data:
            for flag in all_flags.data:
                status = "✓ Enabled" if flag.get("enabled_default") else "✗ Disabled"
                print(f"  - {flag['name']}: {status}")
                if flag.get("description"):
                    print(f"    {flag['description']}")
        else:
            print("  No flags found")
    except Exception as e:
        print(f"  [ERROR] Failed to list flags: {e}")
    
    print("\n" + "=" * 60)
    print("Seed complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Test flag evaluation: Use FeatureFlagService.is_enabled()")
    print("2. Set tenant overrides: PUT /api/v1/admin/flags/{name}/tenants/{tenant_id}")
    print("3. Check flag details: GET /api/v1/admin/flags/{name}")
    print("=" * 60)
    
    return created_flags


def set_tenant_override_example(supabase, flag_name: str, tenant_id: str, enabled: bool):
    """Example: Set a tenant override for a flag."""
    try:
        # Get flag ID
        flag_result = (
            supabase.table("feature_flags")
            .select("id")
            .eq("name", flag_name)
            .limit(1)
            .execute()
        )
        
        if not flag_result.data:
            print(f"  [ERROR] Flag '{flag_name}' not found")
            return False
        
        flag_id = flag_result.data[0]["id"]
        
        # Check if override exists
        existing = (
            supabase.table("tenant_feature_flags")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("flag_id", flag_id)
            .limit(1)
            .execute()
        )
        
        if existing.data:
            # Update
            result = (
                supabase.table("tenant_feature_flags")
                .update({"enabled": enabled})
                .eq("id", existing.data[0]["id"])
                .execute()
            )
            print(f"  [OK] Updated tenant override for '{flag_name}'")
        else:
            # Create
            result = (
                supabase.table("tenant_feature_flags")
                .insert({
                    "tenant_id": tenant_id,
                    "flag_id": flag_id,
                    "enabled": enabled,
                })
                .execute()
            )
            print(f"  [OK] Created tenant override for '{flag_name}'")
        
        return True
        
    except Exception as e:
        print(f"  [ERROR] Failed to set tenant override: {e}")
        return False


if __name__ == "__main__":
    try:
        config = get_auth_config()
    except Exception as e:
        print("ERROR: Failed to load configuration.")
        print("Please ensure you have a .env file with:")
        print("  SUPABASE_URL=...")
        print("  SUPABASE_SERVICE_KEY=...")
        print(f"\nError: {e}")
        exit(1)
    
    if not all([
        config.supabase_url,
        config.supabase_service_key,
    ]):
        print("ERROR: Missing required environment variables.")
        exit(1)
    
    flags = seed_flags()
    
    # Optional: Set example tenant overrides
    # Uncomment and modify to test tenant-specific overrides
    # print("\n" + "=" * 60)
    # print("Setting Example Tenant Overrides")
    # print("=" * 60)
    # 
    # example_tenant_id = "your-tenant-id-here"
    # set_tenant_override_example(
    #     supabase,
    #     "experimental_search",
    #     example_tenant_id,
    #     True
    # )
