"""Audit logger service with async buffering."""
import asyncio
import logging
import threading
from typing import Any
from uuid import UUID

from src.audit.models import AuditEvent
from supabase import Client

logger = logging.getLogger(__name__)

# Global registry to track all active AuditLogger instances for shutdown
_active_loggers: set["AuditLogger"] = set()
_loggers_lock = threading.Lock()
_shutdown_in_progress = threading.Event()


class AuditLogger:
    """
    Async audit logger with buffering for batch inserts.

    Buffers audit events and flushes them in batches to avoid blocking requests.
    Automatically flushes when buffer reaches threshold (10 events) or on explicit flush.
    """

    BUFFER_SIZE = 10

    def __init__(self, supabase: Client, tenant_id: UUID, user_id: UUID | None = None):
        """
        Initialize audit logger.

        Args:
            supabase: Supabase client (with user's JWT for RLS)
            tenant_id: Tenant UUID
            user_id: Optional user UUID (for system events, can be None)
        """
        self.supabase = supabase
        self.tenant_id = tenant_id
        self.user_id = user_id
        self._buffer: list[dict[str, Any]] = []
        self._flush_lock = threading.Lock()

        # Register this instance for shutdown tracking
        with _loggers_lock:
            if not _shutdown_in_progress.is_set():
                _active_loggers.add(self)

    async def log(
        self,
        event_type: str,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """
        Buffer audit event for batch insert.

        Automatically flushes if buffer reaches threshold.
        Non-blocking: errors are logged but don't raise exceptions.

        Args:
            event_type: Event type (e.g., "auth.login")
            action: Action type (create, read, update, delete)
            resource_type: Optional resource type (e.g., "document")
            resource_id: Optional resource identifier
            metadata: Optional additional metadata (must not contain PII)
            ip_address: Optional client IP address
            user_agent: Optional user agent string
        """
        if metadata is None:
            metadata = {}

        event = AuditEvent(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self._buffer.append(event.to_dict())

        # Auto-flush if buffer is full
        if len(self._buffer) >= self.BUFFER_SIZE:
            await self.flush()

    async def flush(self) -> None:
        """
        Batch insert buffered events to database.

        Non-blocking: errors are logged but don't raise exceptions.
        Clears buffer after successful insert.
        Thread-safe: uses lock to prevent concurrent flushes.
        """
        if not self._buffer:
            return

        # Thread-safe flush: prevent concurrent flushes
        with self._flush_lock:
            if not self._buffer:
                return  # Another thread already flushed

            buffer_copy = self._buffer.copy()
            self._buffer = []  # Clear buffer before insert (optimistic)

        try:
            # Use Supabase client with user's JWT (RLS enforced)
            # RLS policy ensures tenant_id matches JWT claims
            self.supabase.table("audit_logs").insert(buffer_copy).execute()

            logger.debug(f"Flushed {len(buffer_copy)} audit log entries for tenant {self.tenant_id}")

        except Exception as e:
            # Log error but don't block request
            # Restore buffer for retry on next flush
            with self._flush_lock:
                self._buffer = buffer_copy + self._buffer

            logger.error(
                f"Failed to flush audit logs for tenant {self.tenant_id}: {e}",
                exc_info=True,
            )
            # Don't raise - audit failures shouldn't break requests

    async def shutdown(self, timeout: float = 5.0) -> bool:
        """
        Flush all buffered events with timeout.

        Called during application shutdown to ensure no audit events are lost.
        Thread-safe and idempotent.

        Args:
            timeout: Maximum seconds to wait for flush to complete

        Returns:
            True if flush completed successfully, False if timeout or error
        """
        # Unregister from global registry
        with _loggers_lock:
            _active_loggers.discard(self)

        if not self._buffer:
            return True

        try:
            # Flush with timeout
            await asyncio.wait_for(self.flush(), timeout=timeout)
            logger.info(
                f"Audit logger shutdown completed for tenant {self.tenant_id}",
                extra={"tenant_id": str(self.tenant_id)},
            )
            return True
        except TimeoutError:
            logger.warning(
                f"Audit logger shutdown timeout for tenant {self.tenant_id}",
                extra={
                    "tenant_id": str(self.tenant_id),
                    "pending_events": len(self._buffer),
                    "timeout_seconds": timeout,
                },
            )
            return False
        except Exception as e:
            logger.error(
                f"Audit logger shutdown error for tenant {self.tenant_id}: {e}",
                extra={
                    "tenant_id": str(self.tenant_id),
                    "pending_events": len(self._buffer),
                },
                exc_info=True,
            )
            return False


def shutdown_all_audit_loggers(timeout: float = 5.0) -> None:
    """
    Shutdown all active audit loggers.

    Called during application shutdown to flush all buffered audit events.
    Thread-safe and handles concurrent shutdown attempts.

    Args:
        timeout: Maximum seconds to wait for all flushes to complete
    """
    global _shutdown_in_progress

    # Mark shutdown in progress (prevents new loggers from registering)
    _shutdown_in_progress.set()

    # Get snapshot of active loggers
    with _loggers_lock:
        loggers_snapshot = list(_active_loggers)
        _active_loggers.clear()

    if not loggers_snapshot:
        logger.debug("No active audit loggers to shutdown")
        return

    logger.info(
        f"Shutting down {len(loggers_snapshot)} audit loggers",
        extra={"logger_count": len(loggers_snapshot)},
    )

    # Flush all loggers concurrently
    async def flush_all() -> None:
        tasks = [logger.shutdown(timeout=timeout) for logger in loggers_snapshot]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)
        failure_count = len(results) - success_count

        if failure_count > 0:
            logger.warning(
                f"Audit logger shutdown completed with {failure_count} failures",
                extra={
                    "total_loggers": len(loggers_snapshot),
                    "success_count": success_count,
                    "failure_count": failure_count,
                },
            )
        else:
            logger.info(
                f"All {success_count} audit loggers flushed successfully",
                extra={"logger_count": success_count},
            )

    # Run in event loop (creates new loop if needed)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, schedule as task
            asyncio.create_task(flush_all())
        else:
            # If loop exists but not running, run until complete
            loop.run_until_complete(flush_all())
    except RuntimeError:
        # No event loop exists, create new one
        asyncio.run(flush_all())
