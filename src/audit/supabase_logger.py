"""Supabase-based immutable audit logger with async writes."""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

try:
    from supabase import Client
except ImportError:
    Client = None

from .models import AuditLogEntry
from ..config.audit_config import get_audit_config
from ..db.supabase_client import get_supabase_client
from ..services.audit_retention import get_tenant_retention_years

logger = logging.getLogger(__name__)


class SupabaseAuditLogger:
    """Immutable audit logger using Supabase PostgreSQL with database-level immutability.
    
    This logger writes audit entries asynchronously to prevent performance
    impact on the main request path. Logs are written to Supabase PostgreSQL
    with database triggers preventing modifications/deletions (WORM storage).
    """
    
    def __init__(
        self,
        config: Optional[Any] = None,
        supabase_client: Optional[Client] = None
    ):
        """Initialize Supabase audit logger.
        
        Args:
            config: Optional AuditConfig instance (uses get_audit_config() if None).
            supabase_client: Optional Supabase client (creates new if None).
        
        Raises:
            ImportError: If supabase is not installed.
            ValueError: If required configuration is missing.
        """
        if Client is None:
            raise ImportError(
                "supabase not installed. Install with: pip install supabase"
            )
        
        self.config = config or get_audit_config()
        
        # Initialize Supabase client
        if supabase_client:
            self.supabase_client = supabase_client
        else:
            self.supabase_client = get_supabase_client(use_service_role=True)
        
        # Async queue for batched writes
        self._queue: asyncio.Queue[AuditLogEntry] = asyncio.Queue(
            maxsize=self.config.audit_queue_size
        )
        self._batch: List[AuditLogEntry] = []
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self) -> None:
        """Start the async flush task."""
        if not self._running:
            self._running = True
            self._flush_task = asyncio.create_task(self._flush_loop())
            logger.info("Supabase audit logger started")
    
    async def stop(self) -> None:
        """Stop the async flush task and flush remaining entries."""
        if self._running:
            self._running = False
            if self._flush_task:
                self._flush_task.cancel()
                try:
                    await self._flush_task
                except asyncio.CancelledError:
                    pass
            
            # Flush remaining entries
            await self._flush_batch()
            logger.info("Supabase audit logger stopped")
    
    async def log(self, entry: AuditLogEntry) -> None:
        """Queue an audit log entry for async writing.
        
        Args:
            entry: Audit log entry to write.
        
        Raises:
            asyncio.QueueFull: If queue is full (should not happen in normal operation).
        """
        try:
            await self._queue.put(entry)
        except asyncio.QueueFull:
            logger.error(
                f"Audit log queue full. Dropping entry: "
                f"user_id={entry.user_id}, action_type={entry.action_type}"
            )
            raise
    
    async def _flush_loop(self) -> None:
        """Background task to periodically flush batched entries."""
        while self._running:
            try:
                # Wait for flush interval or batch size
                await asyncio.sleep(self.config.audit_flush_interval_seconds)
                await self._flush_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in audit flush loop: {e}", exc_info=True)
    
    async def _flush_batch(self) -> None:
        """Flush batched entries to Supabase."""
        # Collect entries from queue
        while not self._queue.empty() and len(self._batch) < self.config.audit_batch_size:
            try:
                entry = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                self._batch.append(entry)
            except asyncio.TimeoutError:
                break
        
        if not self._batch:
            return
        
        # Write batch to Supabase
        try:
            await self._write_batch_to_supabase(self._batch.copy())
            self._batch.clear()
        except Exception as e:
            logger.error(f"Failed to write audit batch to Supabase: {e}", exc_info=True)
            # Keep batch for retry (in production, consider dead letter queue)
    
    def _get_retention_date(self, tenant_id: str) -> datetime:
        """Get retention expiration date for a tenant.
        
        Args:
            tenant_id: Tenant identifier.
        
        Returns:
            Datetime object representing retention expiration date.
        """
        retention_years = get_tenant_retention_years(tenant_id)
        return datetime.utcnow() + timedelta(days=retention_years * 365)
    
    async def _write_batch_to_supabase(self, entries: List[AuditLogEntry]) -> None:
        """Write a batch of entries to Supabase.
        
        Args:
            entries: List of audit log entries to write.
        """
        if not entries:
            return
        
        try:
            # Prepare batch for insertion
            batch_data = []
            for entry in entries:
                retention_date = self._get_retention_date(entry.tenant_id)
                
                batch_data.append({
                    "user_id": entry.user_id,
                    "tenant_id": entry.tenant_id,
                    "timestamp": entry.timestamp,
                    "action_type": entry.action_type,
                    "resource_id": entry.resource_id,
                    "request_metadata": entry.request_metadata,
                    "retention_until": retention_date.isoformat() + "Z"
                })
            
            # Insert batch into Supabase (using control_plane schema)
            # Note: Supabase REST API requires schema.table format or RPC call
            # For now, we'll use the table name and Supabase should find it
            # If using a custom schema, you may need to configure Supabase API settings
            table = self.supabase_client.table("audit_logs")
            result = table.insert(batch_data).execute()
            
            logger.debug(
                f"Wrote {len(entries)} audit entries to Supabase"
            )
            
        except Exception as e:
            error_message = str(e)
            
            # Detect tampering attempts (database triggers will prevent updates/deletes)
            # Note: Supabase errors may indicate constraint violations
            if "immutable" in error_message.lower() or "not allowed" in error_message.lower():
                from .tampering_detector import detect_and_log_tampering_attempt
                # Create a mock exception for tampering detection
                class TamperingError(Exception):
                    pass
                tampering_error = TamperingError(error_message)
                detect_and_log_tampering_attempt(
                    error=tampering_error,
                    operation="InsertAuditLog",
                    tenant_id=entries[0].tenant_id if entries else None,
                    user_id=entries[0].user_id if entries else None,
                    additional_context={"error_message": error_message, "backend": "supabase"}
                )
            
            logger.error(f"Supabase error writing audit logs: {e}", exc_info=True)
            raise
    
    def log_sync(self, entry: AuditLogEntry) -> None:
        """Synchronously write a single audit log entry (for critical operations).
        
        Args:
            entry: Audit log entry to write.
        
        Note:
            This method blocks and should only be used for critical audit events
            that must be logged immediately (e.g., attempted log tampering).
        """
        try:
            retention_date = self._get_retention_date(entry.tenant_id)
            
            data = {
                "user_id": entry.user_id,
                "tenant_id": entry.tenant_id,
                "timestamp": entry.timestamp,
                "action_type": entry.action_type,
                "resource_id": entry.resource_id,
                "request_metadata": entry.request_metadata,
                "retention_until": retention_date.isoformat() + "Z"
            }
            
            table = self.supabase_client.table("audit_logs")
            table.insert(data).execute()
            
            logger.info(f"Synced audit log entry to Supabase: {entry.action_type}")
        except Exception as e:
            from .tampering_detector import detect_and_log_tampering_attempt
            detect_and_log_tampering_attempt(
                error=e,
                operation="InsertAuditLogSync",
                tenant_id=entry.tenant_id,
                user_id=entry.user_id
            )
            logger.error(f"Failed to sync audit log entry: {e}", exc_info=True)
            raise


# Global logger instance (will be set by factory function)
_audit_logger: Optional[Any] = None
