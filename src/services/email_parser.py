"""
Email Parser Service - Ingestion Plane

Parses email content from Resend webhook payloads.
Extracts email metadata, body content, and attachments.
"""

import base64
import email
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Optional
from pydantic import BaseModel, Field


class Attachment(BaseModel):
    """Email attachment model."""
    filename: str
    content_type: str
    content: bytes
    size: int


class ParsedEmail(BaseModel):
    """Parsed email model."""
    from_address: str
    to_address: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    attachments: list[Attachment] = Field(default_factory=list)


class EmailParser:
    """Service for parsing email content from Resend webhook payloads."""
    
    def parse_resend_webhook(self, payload: dict) -> ParsedEmail:
        """
        Parse Resend webhook payload into ParsedEmail model.
        
        Args:
            payload: Resend webhook payload dictionary
            
        Returns:
            ParsedEmail with extracted email data
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Extract email headers
        from_address = self._extract_address(payload.get("from") or "")
        to_address = self._extract_address(payload.get("to") or "")
        subject = payload.get("subject") or ""
        
        # Parse email body
        body_text = ""
        body_html: Optional[str] = None
        
        # Resend provides text and html separately
        if payload.get("text"):
            body_text = payload["text"]
        elif payload.get("html"):
            # Fallback: extract text from HTML if no text version
            body_text = self._html_to_text(payload["html"])
        
        if payload.get("html"):
            body_html = payload["html"]
        
        # Parse attachments
        attachments: list[Attachment] = []
        if payload.get("attachments"):
            for att_data in payload["attachments"]:
                attachment = self._parse_attachment(att_data)
                if attachment:
                    attachments.append(attachment)
        
        return ParsedEmail(
            from_address=from_address,
            to_address=to_address,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
        )
    
    def _extract_address(self, address_string: str) -> str:
        """
        Extract email address from address string.
        
        Handles formats like:
        - "user@example.com"
        - "Name <user@example.com>"
        - "user@example.com, other@example.com" (takes first)
        
        Args:
            address_string: Email address string
            
        Returns:
            Clean email address
        """
        if not address_string:
            return ""
        
        # Parse using email.utils.parseaddr
        name, addr = parseaddr(address_string)
        
        # If parseaddr didn't work, try splitting by comma and taking first
        if not addr:
            parts = address_string.split(",")
            if parts:
                name, addr = parseaddr(parts[0].strip())
        
        return addr or address_string.strip()
    
    def _parse_attachment(self, att_data: dict) -> Optional[Attachment]:
        """
        Parse attachment data from Resend webhook.
        
        Args:
            att_data: Attachment data dictionary
            
        Returns:
            Attachment model or None if invalid
        """
        filename = att_data.get("filename") or att_data.get("name") or "attachment"
        content_type = att_data.get("content_type") or att_data.get("type") or "application/octet-stream"
        
        # Resend provides base64-encoded content
        content_b64 = att_data.get("content") or att_data.get("data")
        if not content_b64:
            return None
        
        try:
            # Decode base64 content
            if isinstance(content_b64, str):
                content = base64.b64decode(content_b64)
            else:
                content = content_b64
            
            size = len(content)
            
            return Attachment(
                filename=filename,
                content_type=content_type,
                content=content,
                size=size,
            )
        except (ValueError, TypeError, base64.binascii.Error) as e:
            # Invalid base64 encoding or type mismatch
            # Return None to skip invalid attachments
            return None
        except Exception as e:
            # Unexpected error - log but don't fail entire email parsing
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "Unexpected error parsing attachment",
                extra={
                    "filename": filename,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            return None
    
    def _html_to_text(self, html: str) -> str:
        """
        Convert HTML to plain text (simple implementation).
        
        Args:
            html: HTML content
            
        Returns:
            Plain text content
        """
        # Simple HTML tag removal (for basic cases)
        # In production, consider using html2text or similar library
        import re
        text = re.sub(r'<[^>]+>', '', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
