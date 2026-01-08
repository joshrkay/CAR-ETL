"""Feature flag service with caching."""
from uuid import UUID
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from supabase import Client
import threading

from src.features.models import FeatureFlagResponse


# Module-level shared cache: {(tenant_id, flag_name): (value, expires_at)}
# This cache is shared across all FeatureFlagService instances for the same tenant
_shared_cache: Dict[Tuple[UUID, str], Tuple[bool, datetime]] = {}
_cache_lock = threading.Lock()  # Thread-safe cache access


class FeatureFlagService:
    """Service for evaluating feature flags per tenant with caching."""
    
    CACHE_TTL_SECONDS = 300  # 5 minutes
    
    def __init__(self, supabase_client: Client, tenant_id: UUID):
        """
        Initialize feature flag service.
        
        Args:
            supabase_client: Supabase client instance
            tenant_id: Current tenant ID
        """
        self.client = supabase_client
        self.tenant_id = tenant_id
    
    def _get_cache_key(self, flag_name: str) -> Tuple[UUID, str]:
        """Get cache key for a flag."""
        return (self.tenant_id, flag_name)
    
    def _is_cache_valid(self, flag_name: str) -> bool:
        """Check if cache entry is still valid."""
        cache_key = self._get_cache_key(flag_name)
        with _cache_lock:
            if cache_key not in _shared_cache:
                return False
            _, expires_at = _shared_cache[cache_key]
            return datetime.utcnow() < expires_at
    
    def _get_cached_value(self, flag_name: str) -> Optional[bool]:
        """Get cached value if valid."""
        if not self._is_cache_valid(flag_name):
            return None
        cache_key = self._get_cache_key(flag_name)
        with _cache_lock:
            value, _ = _shared_cache.get(cache_key, (None, None))
            return value
    
    def _set_cached_value(self, flag_name: str, value: bool) -> None:
        """Set cached value with TTL."""
        cache_key = self._get_cache_key(flag_name)
        expires_at = datetime.utcnow() + timedelta(seconds=self.CACHE_TTL_SECONDS)
        with _cache_lock:
            _shared_cache[cache_key] = (value, expires_at)
    
    def _invalidate_cache(self, flag_name: Optional[str] = None) -> None:
        """
        Invalidate cache for a specific flag or all flags for this tenant.
        
        Args:
            flag_name: If provided, invalidate only this flag. If None, invalidate all flags for tenant.
        """
        with _cache_lock:
            if flag_name:
                cache_key = self._get_cache_key(flag_name)
                _shared_cache.pop(cache_key, None)
            else:
                # Invalidate all cache entries for this tenant
                keys_to_remove = [
                    key for key in _shared_cache.keys()
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
                flag_data = flag_result.data[0]
                flag_id = flag_data["id"]
                default_enabled = flag_data.get("enabled_default", False)
                
                # Check for tenant override
                tenant_override_result = (
                    self.client.table("tenant_feature_flags")
                    .select("enabled")
                    .eq("tenant_id", str(self.tenant_id))
                    .eq("flag_id", str(flag_id))
                    .limit(1)
                    .execute()
                )
                
                if tenant_override_result.data:
                    # Use tenant override
                    result = tenant_override_result.data[0]["enabled"]
                else:
                    # Use default
                    result = default_enabled
            
            # Update shared cache
            self._set_cached_value(flag_name, result)
            return result
            
        except Exception as e:
            # On error, return False (fail closed)
            # In production, you might want to log this
            return False
    
    async def get_all_flags(self) -> Dict[str, bool]:
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
            override_map = {
                override["flag_id"]: override["enabled"]
                for override in (overrides_result.data or [])
            }
            
            # Build result map
            result = {}
            for flag in flags_result.data:
                flag_id = flag["id"]
                flag_name = flag["name"]
                
                if flag_id in override_map:
                    result[flag_name] = override_map[flag_id]
                else:
                    result[flag_name] = flag.get("enabled_default", False)
            
            # Update shared cache for all flags
            for flag_name, enabled in result.items():
                self._set_cached_value(flag_name, enabled)
            
            return result
            
        except Exception as e:
            # On error, return empty dict
            return {}
    
    async def get_flag_details(self, flag_name: str) -> Optional[FeatureFlagResponse]:
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
            
            flag_data = flag_result.data[0]
            flag_id = flag_data["id"]
            default_enabled = flag_data.get("enabled_default", False)
            
            # Check for tenant override
            tenant_override_result = (
                self.client.table("tenant_feature_flags")
                .select("enabled")
                .eq("tenant_id", str(self.tenant_id))
                .eq("flag_id", str(flag_id))
                .limit(1)
                .execute()
            )
            
            is_override = bool(tenant_override_result.data)
            enabled = (
                tenant_override_result.data[0]["enabled"]
                if is_override
                else default_enabled
            )
            
            return FeatureFlagResponse(
                name=flag_name,
                enabled=enabled,
                is_override=is_override,
                description=flag_data.get("description"),
            )
            
        except Exception:
            return None
    
    def invalidate_cache(self, flag_name: Optional[str] = None) -> None:
        """
        Manually invalidate the cache (useful after admin updates).
        
        Args:
            flag_name: If provided, invalidate only this flag. If None, invalidate all flags for tenant.
        """
        self._invalidate_cache(flag_name)
