"""S3-based immutable audit logger with async writes."""
import asyncio
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    from botocore.config import Config
except ImportError:
    boto3 = None
    ClientError = None
    BotoCoreError = None
    Config = None

from .models import AuditLogEntry
from .tampering_detector import detect_and_log_tampering_attempt
from ..config.audit_config import get_audit_config
from ..services.audit_retention import get_tenant_retention_years

logger = logging.getLogger(__name__)


class S3AuditLogger:
    """Immutable audit logger using S3 Object Lock in Compliance Mode.
    
    This logger writes audit entries asynchronously to prevent performance
    impact on the main request path. Logs are written to S3 with Object Lock
    enabled to prevent tampering.
    """
    
    def __init__(
        self,
        config: Optional[Any] = None,
        s3_client: Optional[Any] = None
    ):
        """Initialize S3 audit logger.
        
        Args:
            config: Optional AuditConfig instance (uses get_audit_config() if None).
            s3_client: Optional boto3 S3 client (creates new if None).
        
        Raises:
            ImportError: If boto3 is not installed.
            ValueError: If required configuration is missing.
        """
        if boto3 is None:
            raise ImportError(
                "boto3 not installed. Install with: pip install boto3"
            )
        
        self.config = config or get_audit_config()
        
        if not self.config.audit_s3_bucket:
            raise ValueError("AUDIT_S3_BUCKET environment variable is required")
        
        # Initialize S3 client
        if s3_client:
            self.s3_client = s3_client
        else:
            self.s3_client = self._create_s3_client()
        
        # Async queue for batched writes
        self._queue: asyncio.Queue[AuditLogEntry] = asyncio.Queue(
            maxsize=self.config.audit_queue_size
        )
        self._batch: List[AuditLogEntry] = []
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False
    
    def _create_s3_client(self) -> Any:
        """Create boto3 S3 client with appropriate configuration.
        
        Returns:
            boto3 S3 client instance.
        """
        client_config = Config(
            retries={
                'max_attempts': 3,
                'mode': 'standard'
            }
        )
        
        if self.config.aws_access_key_id and self.config.aws_secret_access_key:
            return boto3.client(
                's3',
                region_name=self.config.audit_s3_region,
                aws_access_key_id=self.config.aws_access_key_id,
                aws_secret_access_key=self.config.aws_secret_access_key,
                config=client_config
            )
        else:
            # Use default credentials (IAM role, environment, etc.)
            return boto3.client(
                's3',
                region_name=self.config.audit_s3_region,
                config=client_config
            )
    
    async def start(self) -> None:
        """Start the async flush task."""
        if not self._running:
            self._running = True
            self._flush_task = asyncio.create_task(self._flush_loop())
            logger.info("S3 audit logger started")
    
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
            logger.info("S3 audit logger stopped")
    
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
        """Flush batched entries to S3."""
        # Collect entries from queue
        while not self._queue.empty() and len(self._batch) < self.config.audit_batch_size:
            try:
                entry = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                self._batch.append(entry)
            except asyncio.TimeoutError:
                break
        
        if not self._batch:
            return
        
        # Write batch to S3
        try:
            await self._write_batch_to_s3(self._batch.copy())
            self._batch.clear()
        except Exception as e:
            logger.error(f"Failed to write audit batch to S3: {e}", exc_info=True)
            # Keep batch for retry (in production, consider dead letter queue)
    
    def _get_retention_date(self, tenant_id: str) -> datetime:
        """Get retention date for a tenant.
        
        Args:
            tenant_id: Tenant identifier.
        
        Returns:
            Datetime object representing retention date.
        """
        retention_years = get_tenant_retention_years(tenant_id)
        return datetime.utcnow().replace(
            year=datetime.utcnow().year + retention_years
        )
    
    async def _write_batch_to_s3(self, entries: List[AuditLogEntry]) -> None:
        """Write a batch of entries to S3.
        
        Args:
            entries: List of audit log entries to write.
        """
        if not entries:
            return
        
        # Group by tenant and date for better organization
        tenant_id = entries[0].tenant_id
        date_str = datetime.utcnow().strftime("%Y/%m/%d")
        
        # Create S3 key: tenant_id/YYYY/MM/DD/timestamp-batch.json
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        s3_key = f"{tenant_id}/{date_str}/{timestamp}-batch.json"
        
        # Convert entries to JSON array
        entries_json = [entry.model_dump() for entry in entries]
        body = json.dumps(entries_json, indent=2)
        
        # Write to S3 with Object Lock retention
        try:
            retention_date = self._get_retention_date(tenant_id)
            
            self.s3_client.put_object(
                Bucket=self.config.audit_s3_bucket,
                Key=s3_key,
                Body=body.encode('utf-8'),
                ContentType='application/json',
                ObjectLockMode='COMPLIANCE',
                ObjectLockRetainUntilDate=retention_date
            )
            
            logger.debug(
                f"Wrote {len(entries)} audit entries to S3: {s3_key}"
            )
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            
            # Detect tampering attempts (e.g., trying to modify locked objects)
            detect_and_log_tampering_attempt(
                error=e,
                operation="PutObject",
                s3_key=s3_key,
                tenant_id=tenant_id,
                user_id=entries[0].user_id if entries else None,
                additional_context={"batch_size": len(entries)}
            )
            
            if error_code == 'InvalidBucketObjectLockConfiguration':
                logger.error(
                    f"S3 bucket {self.config.audit_s3_bucket} does not have "
                    f"Object Lock enabled. Audit logs cannot be written."
                )
            elif error_code == 'AccessDenied':
                logger.error(
                    f"Access denied writing to S3 bucket {self.config.audit_s3_bucket}. "
                    f"Check IAM permissions."
                )
            else:
                logger.error(f"S3 error writing audit logs: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error writing audit logs to S3: {e}", exc_info=True)
            raise
    
    def log_sync(self, entry: AuditLogEntry) -> None:
        """Synchronously write a single audit log entry (for critical operations).
        
        Args:
            entry: Audit log entry to write.
        
        Note:
            This method blocks and should only be used for critical audit events
            that must be logged immediately (e.g., attempted log tampering).
        """
        tenant_id = entry.tenant_id
        date_str = datetime.utcnow().strftime("%Y/%m/%d")
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S.%f")
        s3_key = f"{tenant_id}/{date_str}/{timestamp}-{entry.action_type}.json"
        
        try:
            retention_date = self._get_retention_date(tenant_id)
            
            self.s3_client.put_object(
                Bucket=self.config.audit_s3_bucket,
                Key=s3_key,
                Body=entry.to_json().encode('utf-8'),
                ContentType='application/json',
                ObjectLockMode='COMPLIANCE',
                ObjectLockRetainUntilDate=retention_date
            )
            logger.info(f"Synced audit log entry to S3: {s3_key}")
        except ClientError as e:
            # Detect tampering attempts
            detect_and_log_tampering_attempt(
                error=e,
                operation="PutObject",
                s3_key=s3_key,
                tenant_id=tenant_id,
                user_id=entry.user_id
            )
            logger.error(f"Failed to sync audit log entry: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to sync audit log entry: {e}", exc_info=True)
            raise


# Note: get_audit_logger() is now in logger_factory.py
# This allows switching between S3 and Supabase backends
