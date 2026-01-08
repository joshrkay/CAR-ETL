"""Audit logger service with async buffering."""
import logging
from typing import Optional, Dict, Any
from uuid import UUID
from supabase import Client

from src.audit.models import AuditEvent

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Async audit logger with buffering for batch inserts.
    
    Buffers audit events and flushes them in batches to avoid blocking requests.
    Automatically flushes when buffer reaches threshold (10 events) or on explicit flush.
    """
    
    BUFFER_SIZE = 10
    
    def __init__(self, supabase: Client, tenant_id: UUID, user_id: Optional[UUID] = None):
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
        self._buffer: list[Dict[str, Any]] = []
    
    async def log(
        self,
        event_type: str,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
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
        """
        if not self._buffer:
            return
        
        try:
            # Use Supabase client with user's JWT (RLS enforced)
            # RLS policy ensures tenant_id matches JWT claims
            result = self.supabase.table("audit_logs").insert(self._buffer).execute()
            
            # Clear buffer on success
            buffer_size = len(self._buffer)
            self._buffer = []
            
            logger.debug(f"Flushed {buffer_size} audit log entries for tenant {self.tenant_id}")
            
        except Exception as e:
            # Log error but don't block request
            # Buffer is preserved for retry on next flush
            logger.error(
                f"Failed to flush audit logs for tenant {self.tenant_id}: {e}",
                exc_info=True,
            )
            # Don't raise - audit failures shouldn't break requests
