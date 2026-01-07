"""Rate limiting for authentication attempts."""
from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv6Address
from typing import Union
from supabase import create_client, Client
from src.auth.config import AuthConfig, get_auth_config


IPAddress = Union[IPv4Address, IPv6Address, str]


class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds")


class AuthRateLimiter:
    """Rate limiter for authentication attempts."""

    def __init__(self, config: AuthConfig):
        self.config = config
        self.supabase: Client = create_client(
            config.supabase_url,
            config.supabase_service_key,
        )

    def check_rate_limit(self, ip_address: str) -> None:
        """
        Check if IP address has exceeded rate limit.
        
        Raises:
            RateLimitError: If rate limit is exceeded
        """
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.config.auth_rate_limit_window_seconds)

        try:
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
                record = result.data[0]
                attempt_count = record.get("attempt_count", 0)

                if attempt_count >= self.config.auth_rate_limit_max_attempts:
                    window_start_str = record["window_start"]
                    if isinstance(window_start_str, str):
                        window_start_dt = datetime.fromisoformat(window_start_str.replace("Z", "+00:00"))
                    else:
                        window_start_dt = window_start_str
                    
                    elapsed = (now - window_start_dt.replace(tzinfo=None)).total_seconds()
                    retry_after = max(1, int(self.config.auth_rate_limit_window_seconds - elapsed))
                    raise RateLimitError(retry_after)

                self._increment_attempt(record["id"], attempt_count + 1)
            else:
                self._create_new_record(ip_address, now)

        except RateLimitError:
            raise
        except Exception:
            if self.config.is_production:
                raise

    def _increment_attempt(self, record_id: str, new_count: int) -> None:
        """Increment attempt count for existing record."""
        try:
            self.supabase.table("auth_rate_limits").update({
                "attempt_count": new_count,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", record_id).execute()
        except Exception:
            if self.config.is_production:
                raise

    def _create_new_record(self, ip_address: str, window_start: datetime) -> None:
        """Create new rate limit record."""
        try:
            self.supabase.table("auth_rate_limits").insert({
                "ip_address": ip_address,
                "attempt_count": 1,
                "window_start": window_start.isoformat(),
            }).execute()
        except Exception:
            if self.config.is_production:
                raise

    def reset_rate_limit(self, ip_address: str) -> None:
        """Reset rate limit for IP address (on successful auth)."""
        try:
            self.supabase.table("auth_rate_limits").delete().eq("ip_address", ip_address).execute()
        except Exception:
            if self.config.is_production:
                raise


def get_rate_limiter() -> AuthRateLimiter:
    """Get rate limiter instance."""
    config = get_auth_config()
    return AuthRateLimiter(config)
