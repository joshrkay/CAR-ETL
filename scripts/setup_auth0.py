"""Python-based Auth0 setup script using Management API."""
import sys
import json
from typing import Dict, Any, Optional
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from src.auth.config import get_auth0_config, Auth0Config
from src.auth.auth0_client import Auth0ManagementClient, Auth0TokenError, Auth0APIError


def log_info(message: str) -> None:
    """Log info message."""
    print(f"[INFO] {message}")


def log_warn(message: str) -> None:
    """Log warning message."""
    print(f"[WARN] {message}")


def log_error(message: str) -> None:
    """Log error message."""
    print(f"[ERROR] {message}")


def log_success(message: str) -> None:
    """Log success message."""
    print(f"[SUCCESS] {message}")


def create_api_resource(config: Auth0Config, client: Auth0ManagementClient) -> Optional[str]:
    """Create API resource in Auth0."""
    log_info("Creating API resource 'CAR API'...")
    
    try:
        # Use Management API to create API
        api_data = {
            "name": config.api_name,
            "identifier": config.api_identifier,
            "signing_alg": "RS256",
            "scopes": [
                {"value": "read:documents", "description": "Read document data"},
                {"value": "write:documents", "description": "Create/update documents"},
                {"value": "admin", "description": "Administrative operations"}
            ]
        }
        
        # Get Management API token
        token = client._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = httpx.post(
            f"{config.management_api_url}/resource-servers",
            headers=headers,
            json=api_data,
            timeout=30.0
        )
        
        if response.status_code == 201:
            api_info = response.json()
            log_success(f"API resource created: {api_info.get('id')}")
            return api_info.get('id')
        elif response.status_code == 409:
            log_warn("API resource already exists. Fetching existing API...")
            # Try to find existing API
            list_response = httpx.get(
                f"{config.management_api_url}/resource-servers",
                headers=headers,
                timeout=30.0
            )
            if list_response.status_code == 200:
                apis = list_response.json()
                for api in apis:
                    if api.get('identifier') == config.api_identifier:
                        log_success(f"Found existing API: {api.get('id')}")
                        return api.get('id')
            log_warn("Could not find existing API, but it may exist")
            return None
        else:
            log_error(f"Failed to create API: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        log_error(f"Error creating API resource: {e}")
        return None


def update_api_scopes(config: Auth0Config, client: Auth0ManagementClient, api_id: str) -> bool:
    """Update API scopes."""
    log_info("Updating API scopes...")
    
    try:
        token = client._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        scopes = [
            {"value": "read:documents", "description": "Read document data"},
            {"value": "write:documents", "description": "Create/update documents"},
            {"value": "admin", "description": "Administrative operations"}
        ]
        
        response = httpx.patch(
            f"{config.management_api_url}/resource-servers/{api_id}",
            headers=headers,
            json={"scopes": scopes},
            timeout=30.0
        )
        
        if response.status_code == 200:
            log_success("API scopes updated successfully")
            return True
        else:
            log_warn(f"Could not update scopes: {response.status_code}")
            return False
    except Exception as e:
        log_warn(f"Error updating scopes: {e}")
        return False


def get_database_connections(config: Auth0Config, client: Auth0ManagementClient) -> list:
    """Get list of database connections."""
    try:
        token = client._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = httpx.get(
            f"{config.management_api_url}/connections",
            headers=headers,
            params={"strategy": "auth0"},
            timeout=30.0
        )
        
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        log_error(f"Error fetching connections: {e}")
        return []


def configure_database_connection(
    config: Auth0Config,
    client: Auth0ManagementClient,
    connection_name: str
) -> bool:
    """Configure database connection password policy."""
    log_info(f"Configuring database connection: {connection_name}...")
    
    try:
        connections = get_database_connections(config, client)
        connection_id = None
        
        for conn in connections:
            if conn.get('name') == connection_name:
                connection_id = conn.get('id')
                break
        
        if not connection_id:
            log_warn(f"Connection '{connection_name}' not found. It may need to be created manually.")
            log_warn("Default connection 'Username-Password-Authentication' should exist in Auth0.")
            return False
        
        token = client._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Update password policy
        password_policy = {
            "passwordPolicy": "fair",
            "options": {
                "min_length": 8,
                "require_lowercase": True,
                "require_uppercase": False,
                "require_numbers": True,
                "require_symbols": True
            }
        }
        
        response = httpx.patch(
            f"{config.management_api_url}/connections/{connection_id}",
            headers=headers,
            json=password_policy,
            timeout=30.0
        )
        
        if response.status_code == 200:
            log_success("Database connection password policy configured")
            return True
        else:
            log_warn(f"Could not update connection: {response.status_code} - {response.text[:200]}")
            return False
    except Exception as e:
        log_error(f"Error configuring connection: {e}")
        return False


def verify_jwt_signing(config: Auth0Config, client: Auth0ManagementClient, api_id: str) -> bool:
    """Verify JWT signing algorithm is RS256."""
    log_info("Verifying JWT signing algorithm is RS256...")
    
    try:
        token = client._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = httpx.get(
            f"{config.management_api_url}/resource-servers/{api_id}",
            headers=headers,
            timeout=30.0
        )
        
        if response.status_code == 200:
            api_info = response.json()
            signing_alg = api_info.get('signing_alg', '')
            
            if signing_alg == 'RS256':
                log_success("JWT signing algorithm is RS256")
                return True
            else:
                log_warn(f"JWT signing algorithm is {signing_alg}, updating to RS256...")
                
                update_response = httpx.patch(
                    f"{config.management_api_url}/resource-servers/{api_id}",
                    headers=headers,
                    json={"signing_alg": "RS256"},
                    timeout=30.0
                )
                
                if update_response.status_code == 200:
                    log_success("JWT signing algorithm updated to RS256")
                    return True
                else:
                    log_error(f"Failed to update signing algorithm: {update_response.status_code}")
                    return False
        else:
            log_error(f"Failed to get API info: {response.status_code}")
            return False
    except Exception as e:
        log_error(f"Error verifying JWT signing: {e}")
        return False


def print_management_api_instructions() -> None:
    """Print instructions for creating Management API client."""
    log_info("Management API Machine-to-Machine application setup:")
    print("\n" + "=" * 60)
    print("MANUAL STEP REQUIRED: Create Management API Client")
    print("=" * 60)
    print("1. Go to Auth0 Dashboard: https://manage.auth0.com")
    print("2. Navigate to Applications > Applications")
    print("3. Click '+ Create Application'")
    print("4. Name: 'CAR Platform Management Client'")
    print("5. Type: 'Machine to Machine Applications'")
    print("6. Click 'Create'")
    print("7. Select 'Auth0 Management API' from the dropdown")
    print("8. Toggle 'Authorize'")
    print("9. Grant the following permissions:")
    print("   - read:users")
    print("   - create:users")
    print("   - update:users")
    print("   - delete:users")
    print("   - read:connections")
    print("   - update:connections")
    print("   - read:resource_servers")
    print("   - create:resource_servers")
    print("   - update:resource_servers")
    print("10. Click 'Authorize'")
    print("11. Copy the 'Client ID' and 'Client Secret'")
    print("12. Set environment variables:")
    print("    AUTH0_MANAGEMENT_CLIENT_ID=<your-client-id>")
    print("    AUTH0_MANAGEMENT_CLIENT_SECRET=<your-client-secret>")
    print("=" * 60 + "\n")


def main() -> None:
    """Main setup function."""
    print("=" * 60)
    print("Auth0 Setup for CAR Platform")
    print("=" * 60)
    print()
    
    try:
        config = get_auth0_config()
    except Exception as e:
        log_error(f"Configuration error: {e}")
        print("\nRequired environment variables:")
        print("  - AUTH0_DOMAIN")
        print("  - AUTH0_MANAGEMENT_CLIENT_ID")
        print("  - AUTH0_MANAGEMENT_CLIENT_SECRET")
        print("  - AUTH0_DATABASE_CONNECTION_NAME")
        print("\nExample:")
        print("  AUTH0_DOMAIN=dev-khx88c3lu7wz2dxx.us.auth0.com")
        sys.exit(1)
    
    log_success("Configuration loaded")
    print(f"  Domain: {config.domain}")
    print(f"  API Identifier: {config.api_identifier}")
    print()
    
    # Create Management API client
    try:
        client = Auth0ManagementClient(config)
        if not client.verify_connectivity():
            log_error("Cannot connect to Auth0 Management API")
            print_management_api_instructions()
            sys.exit(1)
        log_success("Connected to Auth0 Management API")
    except (Auth0TokenError, Auth0APIError) as e:
        log_error(f"Auth0 connection failed: {e}")
        print_management_api_instructions()
        sys.exit(1)
    
    print()
    
    # Create API resource
    api_id = create_api_resource(config, client)
    if api_id:
        # Update scopes
        update_api_scopes(config, client, api_id)
        # Verify JWT signing
        verify_jwt_signing(config, client, api_id)
    else:
        log_warn("API resource creation skipped or failed")
    
    print()
    
    # Configure database connection
    configure_database_connection(config, client, config.database_connection_name)
    
    print()
    
    # Management API client instructions
    print_management_api_instructions()
    
    # Setup complete
    print("=" * 60)
    log_success("Auth0 setup complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Complete Management API client setup (see instructions above)")
    print("2. Test connectivity: python scripts/test_jwt_manual.py")
    print("3. Test health endpoint: curl http://localhost:8000/health")
    print()


if __name__ == "__main__":
    main()
