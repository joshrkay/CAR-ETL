"""Feature flag service with caching."""
from uuid import UUID
from datetime import datetime, timedelta
from typing import Dict, Optional
from supabase import Client

from src.features.models import FeatureFlagResponse


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
        self._cache: Dict[str, bool] = {}
        self._cache_expires: Optional[datetime] = None
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if self._cache_expires is None:
            return False
        return datetime.utcnow() < self._cache_expires
    
    def _invalidate_cache(self) -> None:
        """Invalidate the cache."""
        self._cache.clear()
        self._cache_expires = None
    
    async def is_enabled(self, flag_name: str) -> bool:
        """
        Check if a feature flag is enabled for the current tenant.
        
        Args:
            flag_name: Name of the feature flag
            
        Returns:
            True if enabled, False otherwise
        """
        # Check cache first
        if self._is_cache_valid() and flag_name in self._cache:
            return self._cache[flag_name]
        
        # Cache miss or expired - fetch from database
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
            
            # Update cache
            if not self._is_cache_valid():
                self._cache_expires = datetime.utcnow() + timedelta(seconds=self.CACHE_TTL_SECONDS)
            
            self._cache[flag_name] = result
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
            
            # Update cache
            if not self._is_cache_valid():
                self._cache_expires = datetime.utcnow() + timedelta(seconds=self.CACHE_TTL_SECONDS)
            
            for flag_name, enabled in result.items():
                self._cache[flag_name] = enabled
            
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
    
    def invalidate_cache(self) -> None:
        """Manually invalidate the cache (useful after admin updates)."""
        self._invalidate_cache()
