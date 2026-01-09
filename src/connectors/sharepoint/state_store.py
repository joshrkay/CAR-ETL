"""Temporary state storage for OAuth flows."""
import logging
from typing import Optional
from datetime import datetime, timedelta, timezone
from supabase import Client

logger = logging.getLogger(__name__)


def _redact_value(value: str, prefix_len: int = 8) -> str:
    """
    Redact a sensitive value for logging.
    
    Args:
        value: Value to redact
        prefix_len: Number of characters to show from the start
        
    Returns:
        Redacted string showing only prefix with "..."
    """
    if not value or len(value) <= prefix_len:
        return "***"
    
    return f"{value[:prefix_len]}..."


class OAuthStateStore:
    """Stores OAuth state with tenant_id for callback validation."""
    
    def __init__(self, supabase: Client):
        """
        Initialize state store.
        
        Args:
            supabase: Supabase client (service role for cross-tenant access)
        """
        self.supabase = supabase
    
    async def store_state(
        self,
        state: str,
        tenant_id: str,
        expires_in_seconds: int = 600,
    ) -> None:
        """
        Store OAuth state with tenant_id.
        
        Args:
            state: OAuth state parameter
            tenant_id: Tenant identifier
            expires_in_seconds: State expiration time (default: 10 minutes)
            
        Raises:
            Exception: If state storage fails
        """
        if not state:
            logger.error("Attempted to store empty OAuth state")
            raise ValueError("State parameter cannot be empty")
        
        if not tenant_id:
            logger.error("Attempted to store OAuth state with empty tenant_id")
            raise ValueError("Tenant ID cannot be empty")
        
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
        
        try:
            self.supabase.table("oauth_states").insert({
                "state": state,
                "tenant_id": tenant_id,
                "expires_at": expires_at.isoformat(),
            }).execute()
            
            logger.debug(
                "OAuth state stored successfully",
                extra={
                    "state_prefix": _redact_value(state),
                    "tenant_id_prefix": _redact_value(tenant_id),
                    "expires_in_seconds": expires_in_seconds,
                },
            )
        except Exception as e:
            logger.error(
                "Failed to store OAuth state in database",
                extra={
                    "state_prefix": _redact_value(state),
                    "tenant_id_prefix": _redact_value(tenant_id),
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise
    
    async def get_tenant_id(self, state: str) -> Optional[str]:
        """
        Retrieve tenant_id for OAuth state.
        
        Args:
            state: OAuth state parameter
            
        Returns:
            Tenant ID if state is valid and not expired, None otherwise
        """
        if not state:
            logger.warning("get_tenant_id called with empty state parameter")
            return None
        
        try:
            result = (
                self.supabase.table("oauth_states")
                .select("tenant_id, expires_at")
                .eq("state", state)
                .maybe_single()
                .execute()
            )
            
            if not result.data:
                logger.info(
                    "OAuth state not found in database",
                    extra={
                        "state_prefix": _redact_value(state),
                    },
                )
                return None
            
            # Parse expiration timestamp
            try:
                expires_at = datetime.fromisoformat(result.data["expires_at"].replace("Z", "+00:00"))
            except (ValueError, KeyError, TypeError) as e:
                logger.error(
                    "Invalid expires_at format in OAuth state",
                    extra={
                        "state_prefix": _redact_value(state),
                        "expires_at": result.data.get("expires_at"),
                        "error": str(e),
                    },
                )
                return None
            
            # Check if state has expired
            if datetime.now(timezone.utc) > expires_at:
                logger.info(
                    "OAuth state has expired",
                    extra={
                        "state_prefix": _redact_value(state),
                        "expired_at": expires_at.isoformat(),
                    },
                )
                # Clean up expired state
                try:
                    self.supabase.table("oauth_states").delete().eq("state", state).execute()
                except Exception as cleanup_error:
                    logger.warning(
                        "Failed to cleanup expired OAuth state",
                        extra={"error": str(cleanup_error)},
                    )
                return None
            
            tenant_id = result.data.get("tenant_id")
            
            if not tenant_id:
                logger.error(
                    "OAuth state missing tenant_id",
                    extra={
                        "state_prefix": _redact_value(state),
                    },
                )
                return None
            
            # Clean up used state
            try:
                self.supabase.table("oauth_states").delete().eq("state", state).execute()
                logger.debug(
                    "OAuth state retrieved and cleaned up successfully",
                    extra={
                        "state_prefix": _redact_value(state),
                        "tenant_id": _redact_value(tenant_id),
                    },
                )
            except Exception as cleanup_error:
                logger.warning(
                    "Failed to cleanup used OAuth state",
                    extra={
                        "error": str(cleanup_error),
                        "state_prefix": _redact_value(state),
                    },
                )
            
            return tenant_id
            
        except Exception as e:
            logger.error(
                "Failed to retrieve OAuth state due to database error",
                extra={
                    "state_prefix": _redact_value(state),
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
                exc_info=True,
            )
            return None
