"""
Email Ingestion Service - Ingestion Plane

Handles ingestion of emails into the CAR Platform.
Creates documents for email body and attachments.
"""

import hashlib
import logging
from uuid import UUID, uuid4
from typing import Optional
from supabase import Client

from src.services.email_parser import ParsedEmail, Attachment
from src.services.file_validator import FileValidator
from src.services.file_storage import FileStorageService, StorageUploadError
from src.services.redaction import presidio_redact, presidio_redact_bytes
from src.utils.pii_protection import hash_email
from src.exceptions import ValidationError, NotFoundError

logger = logging.getLogger(__name__)

# Maximum file size for email attachments (100MB)
DEFAULT_MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024


class EmailIngestionService:
    """Service for ingesting emails and creating documents."""
    
    def __init__(self, supabase_client: Client):
        """
        Initialize email ingestion service.
        
        Args:
            supabase_client: Supabase client with service_role key
        """
        self.client = supabase_client
        self.validator = FileValidator(max_file_size=DEFAULT_MAX_FILE_SIZE_BYTES)
    
    def ingest_email(
        self,
        parsed_email: ParsedEmail,
        tenant_id: UUID,
    ) -> dict:
        """
        Ingest email and create documents for body and attachments.
        
        Args:
            parsed_email: Parsed email data
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with ingestion results:
            {
                "email_ingestion_id": str,
                "body_document_id": str,
                "attachment_document_ids": list[str],
            }
            
        Raises:
            ValidationError: If email data is invalid
            NotFoundError: If tenant not found
        """
        # Step 1: Verify tenant exists
        self._verify_tenant(tenant_id)
        
        # Step 2: Create document for email body
        body_document_id: Optional[str] = None
        if parsed_email.body_text:
            body_document_id = self._create_body_document(
                parsed_email=parsed_email,
                tenant_id=tenant_id,
            )
        
        # Step 3: Create documents for attachments
        attachment_document_ids: list[str] = []
        for attachment in parsed_email.attachments:
            try:
                doc_id = self._create_attachment_document(
                    attachment=attachment,
                    tenant_id=tenant_id,
                    parent_id=body_document_id,
                )
                if doc_id:
                    attachment_document_ids.append(doc_id)
            except Exception as e:
                logger.warning(
                    "Failed to create document for attachment",
                    extra={
                        "tenant_id": str(tenant_id),
                        "filename": attachment.filename,
                        "error": str(e),
                    },
                )
        
        # Step 4: Create email_ingestions record
        email_ingestion_id = self._create_email_ingestion_record(
            parsed_email=parsed_email,
            tenant_id=tenant_id,
            body_document_id=body_document_id,
            attachment_count=len(attachment_document_ids),
        )
        
        logger.info(
            "Email ingested successfully",
            extra={
                "email_ingestion_id": email_ingestion_id,
                "tenant_id": str(tenant_id),
                "from_address_hash": hash_email(parsed_email.from_address),
                "body_document_id": body_document_id,
                "attachment_count": len(attachment_document_ids),
            },
        )
        
        return {
            "email_ingestion_id": email_ingestion_id,
            "body_document_id": body_document_id,
            "attachment_document_ids": attachment_document_ids,
        }
    
    def _verify_tenant(self, tenant_id: UUID) -> None:
        """
        Verify tenant exists and is active.
        
        Only allows ingestion for tenants with status 'active' to prevent
        data ingestion into inactive or suspended accounts.
        
        Args:
            tenant_id: Tenant identifier
            
        Raises:
            NotFoundError: If tenant not found or not active
        """
        result = (
            self.client.table("tenants")
            .select("id")
            .eq("id", str(tenant_id))
            .eq("status", "active")
            .maybe_single()
            .execute()
        )
        
        if not result.data:
            raise NotFoundError(resource_type="Tenant", resource_id=str(tenant_id))
    
    def _create_body_document(
        self,
        parsed_email: ParsedEmail,
        tenant_id: UUID,
    ) -> str:
        """
        Create document for email body.
        
        SECURITY: Explicitly redacts PII before persisting.
        
        Args:
            parsed_email: Parsed email data
            tenant_id: Tenant identifier
            
        Returns:
            Document ID
            
        Raises:
            ValidationError: If body content is invalid
        """
        # SECURITY: Explicit redaction before persisting (defense in depth)
        redacted_body_text = presidio_redact(parsed_email.body_text)
        body_content = redacted_body_text.encode("utf-8")
        file_hash = self._calculate_hash(body_content)
        
        # Validate body content (as text/plain)
        validation_result = self.validator.validate_file(
            content=body_content,
            claimed_mime="text/plain",
        )
        
        if not validation_result.valid:
            raise ValidationError(
                message="Email body validation failed",
                details=[{"field": "body", "issue": err} for err in validation_result.errors],
            )
        
        # Generate storage path (placeholder - in production, upload to S3)
        document_id = str(uuid4())
        storage_path = f"emails/{tenant_id}/{document_id}/body.txt"
        
        # Create document record
        # Sanitize subject for filename
        safe_subject = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in parsed_email.subject[:50]).strip()
        if not safe_subject:
            safe_subject = "email_body"
        
        document_data = {
            "id": document_id,
            "tenant_id": str(tenant_id),
            "file_hash": file_hash,
            "storage_path": storage_path,
            "original_filename": f"{safe_subject}.txt",
            "mime_type": "text/plain",
            "file_size_bytes": len(body_content),
            "source_type": "email",
            "source_path": parsed_email.from_address,
            "uploaded_by": None,  # Email ingestion has no user
            "status": "pending",
        }
        
        result = self.client.table("documents").insert(document_data).execute()
        
        if not result.data:
            raise Exception("Failed to create body document")
        
        return document_id
    
    def _create_attachment_document(
        self,
        attachment: Attachment,
        tenant_id: UUID,
        parent_id: Optional[str],
    ) -> Optional[str]:
        """
        Create document for email attachment.
        
        SECURITY: Explicitly redacts PII before persisting.
        
        Args:
            attachment: Attachment data
            tenant_id: Tenant identifier
            parent_id: Parent document ID (body document)
            
        Returns:
            Document ID or None if validation fails
        """
        # SECURITY: Explicit redaction before persisting (defense in depth)
        redacted_content = presidio_redact_bytes(
            attachment.content,
            attachment.content_type,
        )
        
        # Validate attachment (using redacted content)
        validation_result = self.validator.validate_file(
            content=redacted_content,
            claimed_mime=attachment.content_type,
        )
        
        if not validation_result.valid:
            logger.warning(
                "Attachment validation failed",
                extra={
                    "tenant_id": str(tenant_id),
                    "filename": attachment.filename,
                    "errors": validation_result.errors,
                },
            )
            return None
        
        # Calculate hash (using redacted content)
        file_hash = self._calculate_hash(redacted_content)
        
        # Generate storage path
        document_id = str(uuid4())
        storage_path = f"emails/{tenant_id}/{document_id}/{attachment.filename}"
        
        # Create document record
        document_data = {
            "id": document_id,
            "tenant_id": str(tenant_id),
            "file_hash": file_hash,
            "storage_path": storage_path,
            "original_filename": attachment.filename,
            "mime_type": validation_result.mime_type,
            "file_size_bytes": attachment.size,
            "source_type": "email",
            "source_path": attachment.filename,
            "parent_id": parent_id,
            "uploaded_by": None,
            "status": "pending",
        }
        
        result = self.client.table("documents").insert(document_data).execute()
        
        if not result.data:
            logger.error(
                "Failed to create attachment document",
                extra={
                    "tenant_id": str(tenant_id),
                    "filename": attachment.filename,
                },
            )
            return None
        
        return document_id
    
    def _create_email_ingestion_record(
        self,
        parsed_email: ParsedEmail,
        tenant_id: UUID,
        body_document_id: Optional[str],
        attachment_count: int,
    ) -> str:
        """
        Create email_ingestions record.
        
        Args:
            parsed_email: Parsed email data
            tenant_id: Tenant identifier
            body_document_id: Body document ID
            attachment_count: Number of attachments processed
            
        Returns:
            Email ingestion ID
        """
        ingestion_data = {
            "tenant_id": str(tenant_id),
            "from_address": parsed_email.from_address,
            "to_address": parsed_email.to_address,
            "subject": parsed_email.subject,
            "body_document_id": body_document_id,
            "attachment_count": attachment_count,
        }
        
        result = self.client.table("email_ingestions").insert(ingestion_data).execute()
        
        if not result.data:
            raise Exception("Failed to create email ingestion record")
        
        return result.data[0]["id"]
    
    def _calculate_hash(self, content: bytes) -> str:
        """
        Calculate SHA-256 hash of content.
        
        Args:
            content: Content bytes
            
        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(content).hexdigest()
