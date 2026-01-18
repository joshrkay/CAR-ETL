"""Temporary state storage for OAuth flows."""
import logging
from typing import Optional, Dict, Any, cast
from datetime import datetime, timedelta, timezone
from supabase import Client

logger = logging.getLogger(__name__)


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
        """
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
        
        # Log storage attempt for traceability
        state_preview = state[:8] if len(state) >= 8 else state
        logger.debug(
            f"Storing OAuth state: state_preview={state_preview}..., "
            f"tenant_id={tenant_id}, expires_in={expires_in_seconds}s"
        )
        
        try:
            self.supabase.table("oauth_states").insert({
                "state": state,
                "tenant_id": tenant_id,
                "expires_at": expires_at.isoformat(),
            }).execute()
            logger.debug(f"Successfully stored OAuth state for tenant_id={tenant_id}")
        except Exception as e:
            logger.error(
                f"Failed to store OAuth state: {str(e)} "
                f"(state_preview={state_preview}..., tenant_id={tenant_id})",
                exc_info=True
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
        state_preview = state[:8] if len(state) >= 8 else state
        logger.debug(f"Retrieving tenant_id for OAuth state: state_preview={state_preview}...")
        
        try:
            result = (
                self.supabase.table("oauth_states")
                .select("tenant_id, expires_at")
                .eq("state", state)
                .maybe_single()
                .execute()
            )
            
            if not result.data:
                logger.debug(f"No OAuth state found for state_preview={state_preview}...")
                return None
            
            # Type narrowing: result.data is not None after the check above
            assert result.data is not None
            data = cast(Dict[str, Any], result.data)
            
            # Safely access expires_at - if missing, treat as corrupted and clean up
            try:
                expires_at_str = data.get("expires_at")
                if not expires_at_str:
                    # Missing expires_at - treat as corrupted, clean up and return None
                    logger.warning(
                        f"OAuth state missing expires_at field: state_preview={state_preview}..., "
                        "treating as corrupted and cleaning up"
                    )
                    self.supabase.table("oauth_states").delete().eq("state", state).execute()
                    return None
                
                expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            except (KeyError, AttributeError, TypeError, ValueError) as e:
                # Corrupted expires_at - clean up corrupted state
                logger.error(
                    f"OAuth state has invalid expires_at field: state_preview={state_preview}..., "
                    f"error={str(e)}, cleaning up corrupted state",
                    exc_info=True
                )
                self.supabase.table("oauth_states").delete().eq("state", state).execute()
                return None
            
            if datetime.now(timezone.utc) > expires_at:
                # CRITICAL: Delete expired state first, then log tenant_id if available
                # This ensures cleanup happens even if tenant_id access fails
                self.supabase.table("oauth_states").delete().eq("state", state).execute()
                
                # Safely access tenant_id for logging - don't let logging failure prevent cleanup
                try:
                    tenant_id = data.get("tenant_id", "unknown")
                    logger.debug(
                        f"OAuth state expired and deleted: state_preview={state_preview}..., "
                        f"tenant_id={tenant_id}, expired_at={expires_at.isoformat()}"
                    )
                except (KeyError, AttributeError, TypeError) as log_error:
                    # Log without tenant_id if access fails - cleanup already completed
                    logger.debug(
                        f"OAuth state expired and deleted: state_preview={state_preview}..., "
                        f"expired_at={expires_at.isoformat()} (tenant_id unavailable: {str(log_error)})"
                    )
                
                return None
            
            tenant_id = str(data.get("tenant_id", ""))
            logger.debug(
                f"Successfully retrieved OAuth state: state_preview={state_preview}..., "
                f"tenant_id={tenant_id}"
            )
            
            # Clean up state after successful retrieval
            self.supabase.table("oauth_states").delete().eq("state", state).execute()
            logger.debug(f"Cleaned up OAuth state for tenant_id={tenant_id}")
            
            return tenant_id
            
        except Exception as e:
            logger.error(
                f"Failed to retrieve OAuth state: {str(e)} "
                f"(state_preview={state_preview}...)",
                exc_info=True
            )
            return None
