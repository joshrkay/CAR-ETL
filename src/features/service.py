"""Feature flag service with caching."""
from typing import Any, cast
from uuid import UUID

from cachetools import TTLCache

from src.features.models import FeatureFlagResponse
from supabase import Client

# Cache configuration
CACHE_TTL_SECONDS = 300  # 5 minutes
CACHE_MAX_SIZE = 1000

# Module-level shared cache with TTL support
# This cache is shared across all FeatureFlagService instances and provides
# thread-safe atomic operations with automatic expiration
_shared_cache: TTLCache[tuple[UUID, str], bool] = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL_SECONDS)


class FeatureFlagService:
    """Service for evaluating feature flags per tenant with caching."""

    def __init__(self, supabase_client: Client, tenant_id: UUID):
        """
        Initialize feature flag service.

        Args:
            supabase_client: Supabase client instance
            tenant_id: Current tenant ID
        """
        self.client = supabase_client
        self.tenant_id = tenant_id

    def _get_cache_key(self, flag_name: str) -> tuple[UUID, str]:
        """Get cache key for a flag."""
        return (self.tenant_id, flag_name)

    def _get_cached_value(self, flag_name: str) -> bool | None:
        """Get cached value if valid. TTLCache handles expiration automatically."""
        cache_key = self._get_cache_key(flag_name)
        cached = _shared_cache.get(cache_key)
        return cast(bool | None, cached)

    def _set_cached_value(self, flag_name: str, value: bool) -> None:
        """Set cached value with TTL. TTLCache handles expiration automatically."""
        cache_key = self._get_cache_key(flag_name)
        _shared_cache[cache_key] = value

    def _invalidate_cache(self, flag_name: str | None = None) -> None:
        """
        Invalidate cache for a specific flag or all flags for this tenant.

        Args:
            flag_name: If provided, invalidate only this flag. If None, invalidate all flags for tenant.
        """
        if flag_name:
            cache_key = self._get_cache_key(flag_name)
            _shared_cache.pop(cache_key, None)
        else:
            # Invalidate all cache entries for this tenant
            keys_to_remove = [
                key for key in list(_shared_cache.keys())
                if key[0] == self.tenant_id
            ]
            for key in keys_to_remove:
                _shared_cache.pop(key, None)

    async def is_enabled(self, flag_name: str) -> bool:
        """
        Check if a feature flag is enabled for the current tenant.

        Uses shared caching to avoid database queries on every check.
        Cache TTL: 5 minutes. Cache is shared across all service instances for the same tenant.

        Args:
            flag_name: Name of the feature flag

        Returns:
            True if enabled, False otherwise (fail closed)
        """
        # Check shared cache first - avoid database query if cache is valid
        cached_value = self._get_cached_value(flag_name)
        if cached_value is not None:
            return cached_value

        # Cache miss or expired - fetch from database (only when needed)
        try:
            # Get the flag definition
            flag_result = (
                self.client.table("feature_flags")
                .select("*")
                .eq("name", flag_name)
                .limit(1)
                .execute()
            )

            if not flag_result.data:
                # Flag doesn't exist, return False
                result = False
            else:
                flag_data = cast(dict[str, Any], flag_result.data[0])
                flag_id = str(flag_data["id"])
                default_enabled = bool(flag_data.get("enabled_default", False))

                # Check for tenant override
                tenant_override_result = (
                    self.client.table("tenant_feature_flags")
                    .select("enabled")
                    .eq("tenant_id", str(self.tenant_id))
                    .eq("flag_id", flag_id)
                    .limit(1)
                    .execute()
                )

                if tenant_override_result.data:
                    # Use tenant override
                    override_data = cast(dict[str, Any], tenant_override_result.data[0])
                    result = bool(override_data.get("enabled", False))
                else:
                    # Use default
                    result = default_enabled

            # Update shared cache
            self._set_cached_value(flag_name, result)
            return result

        except Exception:
            # On error, return False (fail closed)
            # In production, you might want to log this
            return False

    async def get_all_flags(self) -> dict[str, bool]:
        """
        Get all feature flags for the current tenant.

        Returns:
            Dictionary mapping flag names to enabled status
        """
        try:
            # Get all flags
            flags_result = (
                self.client.table("feature_flags")
                .select("*")
                .execute()
            )

            if not flags_result.data:
                return {}

            # Get all tenant overrides for this tenant
            overrides_result = (
                self.client.table("tenant_feature_flags")
                .select("flag_id, enabled")
                .eq("tenant_id", str(self.tenant_id))
                .execute()
            )

            # Build override map
            override_map: dict[str, bool] = {}
            if overrides_result.data:
                for override in overrides_result.data:
                    override_dict = cast(dict[str, Any], override)
                    flag_id = str(override_dict.get("flag_id", ""))
                    enabled = bool(override_dict.get("enabled", False))
                    override_map[flag_id] = enabled

            # Build result map
            result: dict[str, bool] = {}
            if flags_result.data:
                for flag in flags_result.data:
                    flag_dict = cast(dict[str, Any], flag)
                    flag_id = str(flag_dict.get("id", ""))
                    flag_name = str(flag_dict.get("name", ""))

                    if flag_id in override_map:
                        result[flag_name] = override_map[flag_id]
                    else:
                        result[flag_name] = bool(flag_dict.get("enabled_default", False))

            # Update shared cache for all flags
            for flag_name, enabled in result.items():
                self._set_cached_value(flag_name, enabled)

            return result

        except Exception:
            # On error, return empty dict
            return {}

    async def get_flag_details(self, flag_name: str) -> FeatureFlagResponse | None:
        """
        Get detailed information about a flag.

        Args:
            flag_name: Name of the feature flag

        Returns:
            FeatureFlagResponse if flag exists, None otherwise
        """
        try:
            # Get the flag definition
            flag_result = (
                self.client.table("feature_flags")
                .select("*")
                .eq("name", flag_name)
                .limit(1)
                .execute()
            )

            if not flag_result.data:
                return None

            flag_data = cast(dict[str, Any], flag_result.data[0])
            flag_id = str(flag_data.get("id", ""))
            default_enabled = bool(flag_data.get("enabled_default", False))

            # Check for tenant override
            tenant_override_result = (
                self.client.table("tenant_feature_flags")
                .select("enabled")
                .eq("tenant_id", str(self.tenant_id))
                .eq("flag_id", flag_id)
                .limit(1)
                .execute()
            )

            is_override = bool(tenant_override_result.data)
            if is_override and tenant_override_result.data:
                override_data = cast(dict[str, Any], tenant_override_result.data[0])
                enabled = bool(override_data.get("enabled", False))
            else:
                enabled = default_enabled

            return FeatureFlagResponse(
                name=flag_name,
                enabled=enabled,
                is_override=is_override,
                description=flag_data.get("description"),
            )

        except Exception:
            return None

    def invalidate_cache(self, flag_name: str | None = None) -> None:
        """
        Manually invalidate the cache (useful after admin updates).

        Args:
            flag_name: If provided, invalidate only this flag. If None, invalidate all flags for tenant.
        """
        self._invalidate_cache(flag_name)
