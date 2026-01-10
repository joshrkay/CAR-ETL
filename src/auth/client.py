"""Supabase client factory for user requests with RLS support."""

from src.auth.config import AuthConfig, get_auth_config
from supabase import Client, create_client


def create_user_client(access_token: str, config: AuthConfig | None = None) -> Client:
    """
    Create Supabase client that respects RLS using user's JWT token.

    This client uses the anon_key with the user's JWT in the Authorization header.
    Supabase RLS policies will automatically filter data based on the tenant_id
    extracted from the JWT claims.

    Args:
        access_token: User's JWT access token from Authorization header
        config: Optional AuthConfig instance (uses get_auth_config() if not provided)

    Returns:
        Supabase client configured with user's JWT for RLS enforcement

    Note:
        This client uses anon_key, NOT service_key, so RLS policies are enforced.
        Never use service_key for user requests - it bypasses RLS.
    """
    if config is None:
        config = get_auth_config()

    # Create client with anon_key and custom headers containing user's JWT
    # The Supabase client will use this JWT for RLS policy evaluation
    client = create_client(
        config.supabase_url,
        config.supabase_anon_key,  # Use anon_key, not service_key!
    )

    # Set the Authorization header with user's JWT token
    # This ensures RLS policies can extract tenant_id from the token
    client.postgrest.session.headers.update({
        "Authorization": f"Bearer {access_token}"
    })

    return client


def create_service_client(config: AuthConfig | None = None) -> Client:
    """
    Create Supabase client with service_role key (bypasses RLS).

    WARNING: This client bypasses RLS and should ONLY be used for:
    - Admin operations (tenant provisioning, system configuration)
    - Background jobs
    - Operations that require cross-tenant access

    NEVER use this for regular user requests.

    Args:
        config: Optional AuthConfig instance (uses get_auth_config() if not provided)

    Returns:
        Supabase client with service_role key (bypasses RLS)
    """
    if config is None:
        config = get_auth_config()

    return create_client(
        config.supabase_url,
        config.supabase_service_key,  # service_key bypasses RLS
    )
