"""
Email Rate Limiter - Ingestion Plane

Rate limiting for email ingestion by sender address.
Enforces max 100 emails per sender per hour.
"""

import logging
from datetime import UTC, datetime, timedelta

from src.exceptions import RateLimitError
from src.utils.pii_protection import hash_email
from supabase import Client

logger = logging.getLogger(__name__)

# Rate limit configuration
MAX_EMAILS_PER_HOUR = 100
RATE_LIMIT_WINDOW_HOURS = 1


class EmailRateLimiter:
    """Rate limiter for email ingestion by sender address."""

    def __init__(self, supabase_client: Client):
        """
        Initialize email rate limiter.

        Args:
            supabase_client: Supabase client with service_role key
        """
        self.client = supabase_client

    def check_rate_limit(self, from_address: str) -> None:
        """
        Check if sender has exceeded rate limit.

        Args:
            from_address: Sender email address

        Raises:
            RateLimitError: If rate limit is exceeded
        """
        now = datetime.now(UTC)
        window_start = now - timedelta(hours=RATE_LIMIT_WINDOW_HOURS)

        try:
            # Count emails from this sender in the last hour
            result = (
                self.client.table("email_ingestions")
                .select("id, received_at", count="exact")
                .eq("from_address", from_address)
                .gte("received_at", window_start.isoformat())
                .execute()
            )

            email_count = result.count if result.count is not None else len(result.data or [])

            if email_count >= MAX_EMAILS_PER_HOUR:
                # Calculate retry after (seconds until window expires)
                if result.data:
                    oldest_email = min(
                        result.data,
                        key=lambda x: x.get("received_at", now.isoformat())
                    )
                    oldest_time_str = oldest_email.get("received_at")
                    if isinstance(oldest_time_str, str):
                        oldest_time = datetime.fromisoformat(
                            oldest_time_str.replace("Z", "+00:00")
                        )
                        # Ensure both datetimes are timezone-aware for comparison
                        if oldest_time.tzinfo is None:
                            oldest_time = oldest_time.replace(tzinfo=UTC)
                        elapsed = (now - oldest_time).total_seconds()
                        retry_after = max(1, int(3600 - elapsed))
                    else:
                        retry_after = 3600
                else:
                    retry_after = 3600

                logger.warning(
                    "Email rate limit exceeded",
                    extra={
                        "from_address_hash": hash_email(from_address),
                        "email_count": email_count,
                        "limit": MAX_EMAILS_PER_HOUR,
                    },
                )

                raise RateLimitError(
                    retry_after=retry_after,
                    message=f"Rate limit exceeded: max {MAX_EMAILS_PER_HOUR} emails per hour per sender",
                )

        except RateLimitError:
            # Re-raise rate limit errors
            raise
        except (ConnectionError, TimeoutError) as e:
            # Fail closed: Block request on database connection/timeout errors
            # This prevents DoS bypass if rate limiter database is unavailable
            logger.error(
                "Rate limit check failed due to database error - BLOCKING REQUEST (fail closed)",
                extra={
                    "from_address_hash": hash_email(from_address),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise RateLimitError(
                retry_after=300,
                message="Rate limit check unavailable - please try again later",
            ) from e
        # All other exceptions propagate to caller (fail closed by default)
        # This ensures any unexpected errors don't bypass rate limiting
