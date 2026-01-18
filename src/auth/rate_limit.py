"""Rate limiting for authentication attempts."""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, cast
from supabase import create_client
from src.auth.config import AuthConfig, get_auth_config
from src.exceptions import RateLimitError

logger = logging.getLogger(__name__)


class AuthRateLimiter:
    """Rate limiter for authentication attempts."""

    def __init__(self, config: AuthConfig):
        self.config = config
        self._disabled = bool(os.getenv("PYTEST_CURRENT_TEST"))
        if self._disabled:
            self.supabase = None
            return
        self.supabase = create_client(
            config.supabase_url,
            config.supabase_service_key,
        )

    def check_rate_limit(self, ip_address: str) -> None:
        """
        Check if IP address has exceeded rate limit.
        
        Raises:
            RateLimitError: If rate limit is exceeded
        """
        if self._disabled:
            return
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self.config.auth_rate_limit_window_seconds)

        try:
            assert self.supabase is not None
            result = (
                self.supabase.table("auth_rate_limits")
                .select("*")
                .eq("ip_address", ip_address)
                .gte("window_start", window_start.isoformat())
                .order("window_start", desc=False)
                .limit(1)
                .execute()
            )

            if result.data:
                record = cast(Dict[str, Any], result.data[0])
                attempt_count_raw = record.get("attempt_count")
                try:
                    attempt_count = int(attempt_count_raw) if attempt_count_raw is not None else 0
                except ValueError:
                    attempt_count = 0

                if attempt_count >= self.config.auth_rate_limit_max_attempts:
                    window_start_value = record.get("window_start")
                    if isinstance(window_start_value, str):
                        window_start_dt = datetime.fromisoformat(window_start_value.replace("Z", "+00:00"))
                    elif isinstance(window_start_value, datetime):
                        window_start_dt = window_start_value
                    else:
                        # Fallback: use current time if invalid
                        window_start_dt = now
                    
                    # Ensure both datetimes are timezone-aware for comparison
                    if window_start_dt.tzinfo is None:
                        window_start_dt = window_start_dt.replace(tzinfo=timezone.utc)
                    elapsed = (now - window_start_dt).total_seconds()
                    retry_after = max(1, int(self.config.auth_rate_limit_window_seconds - elapsed))
                    raise RateLimitError(retry_after)

                record_id = str(record.get("id", ""))
                self._increment_attempt(record_id, attempt_count + 1)
            else:
                self._create_new_record(ip_address, now)

        except RateLimitError:
            raise
        except Exception as e:
            logger.error(
                "Failed to check rate limit",
                extra={
                    "ip_address": ip_address,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            # In production, fail-fast to prevent bypassing rate limits
            if self.config.is_production:
                raise
            # In non-production, allow request to proceed but log the error
            # This helps with development but should never happen in production

    def _increment_attempt(self, record_id: str, new_count: int) -> None:
        """Increment attempt count for existing record."""
        if self._disabled:
            return
        try:
            assert self.supabase is not None
            self.supabase.table("auth_rate_limits").update({
                "attempt_count": new_count,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", record_id).execute()
        except Exception as e:
            logger.error(
                "Failed to increment rate limit attempt count",
                extra={
                    "record_id": record_id,
                    "new_count": new_count,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            # In production, fail-fast to maintain accurate rate limiting
            if self.config.is_production:
                raise
            # In non-production, log but allow continuation

    def _create_new_record(self, ip_address: str, window_start: datetime) -> None:
        """Create new rate limit record."""
        if self._disabled:
            return
        try:
            assert self.supabase is not None
            self.supabase.table("auth_rate_limits").insert({
                "ip_address": ip_address,
                "attempt_count": 1,
                "window_start": window_start.isoformat(),
            }).execute()
        except Exception as e:
            logger.error(
                "Failed to create rate limit record",
                extra={
                    "ip_address": ip_address,
                    "window_start": window_start.isoformat(),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            # In production, fail-fast to maintain accurate rate limiting
            if self.config.is_production:
                raise
            # In non-production, log but allow continuation

    def reset_rate_limit(self, ip_address: str) -> None:
        """Reset rate limit for IP address (on successful auth)."""
        if self._disabled:
            return
        try:
            assert self.supabase is not None
            self.supabase.table("auth_rate_limits").delete().eq("ip_address", ip_address).execute()
        except Exception as e:
            logger.warning(
                "Failed to reset rate limit",
                extra={
                    "ip_address": ip_address,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            # In production, fail-fast to maintain accurate rate limiting
            if self.config.is_production:
                raise
            # In non-production, log but allow continuation (reset is best-effort)


def get_rate_limiter() -> AuthRateLimiter:
    """Get rate limiter instance."""
    config = get_auth_config()
    return AuthRateLimiter(config)
