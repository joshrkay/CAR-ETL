"""Example usage of Auth0 integration for CAR Platform."""
from typing import Dict, Any

from .auth0_client import Auth0ManagementClient, Auth0TokenError, Auth0APIError
from .config import get_auth0_config


def example_user_operations() -> None:
    """Example: Create, read, update, and delete user operations."""
    config = get_auth0_config()
    client = Auth0ManagementClient(config)

    try:
        # Verify connectivity
        if not client.verify_connectivity():
            print("❌ Auth0 connectivity check failed")
            return

        print("✅ Auth0 connectivity verified")

        # Create a new user
        new_user = client.create_user(
            email="test@example.com",
            password="SecurePass123!",
            connection=config.database_connection_name
        )
        print(f"✅ Created user: {new_user['user_id']}")

        # Get user details
        user = client.get_user(new_user["user_id"])
        print(f"✅ Retrieved user: {user['email']}")

        # Update user
        updated_user = client.update_user(
            new_user["user_id"],
            {"email_verified": True}
        )
        print(f"✅ Updated user: {updated_user['email_verified']}")

        # List users
        users = client.list_users(page=0, per_page=10)
        print(f"✅ Listed {len(users)} users")

        # Delete user
        client.delete_user(new_user["user_id"])
        print(f"✅ Deleted user: {new_user['user_id']}")

    except Auth0TokenError as e:
        print(f"❌ Token error: {e}")
    except Auth0APIError as e:
        print(f"❌ API error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    example_user_operations()
