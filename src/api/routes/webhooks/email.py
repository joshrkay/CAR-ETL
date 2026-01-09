"""
Email Webhook Routes - Ingestion Plane

Handles Resend inbound webhook for email ingestion.
"""

import logging
import os
from uuid import UUID
from fastapi import APIRouter, Request, HTTPException, status, Header
from pydantic import BaseModel
from typing import Optional, Annotated

from src.services.email_parser import EmailParser
from src.services.email_ingestion import EmailIngestionService
from src.services.email_rate_limiter import EmailRateLimiter
from src.services.resend_verifier import ResendVerifier
from src.dependencies import get_service_client
from src.exceptions import RateLimitError, ValidationError, NotFoundError
from src.utils.pii_protection import hash_email
from supabase import Client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/webhooks/email",
    tags=["webhooks"],
)

# Get Resend webhook secret from environment
RESEND_WEBHOOK_SECRET = os.getenv("RESEND_WEBHOOK_SECRET", "")

# Get email ingestion domain from environment (default: ingest.yourapp.com)
EMAIL_INGEST_DOMAIN = os.getenv("EMAIL_INGEST_DOMAIN", "ingest.yourapp.com")


class EmailWebhookResponse(BaseModel):
    """Response model for email webhook."""
    success: bool
    message: str
    email_ingestion_id: Optional[str] = None


@router.post(
    "/inbound",
    response_model=EmailWebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Resend inbound email webhook",
    description="""
    Webhook endpoint for Resend inbound emails.
    
    Security:
    - Verifies Resend signature using HMAC-SHA256
    - Extracts tenant slug from recipient email ({slug}@{EMAIL_INGEST_DOMAIN})
    - Rate limits: max 100 emails per sender per hour
    
    Processing:
    - Parses email (from, to, subject, body, attachments)
    - Creates document for email body
    - Creates documents for each attachment (with parent_id)
    - Records email ingestion event
    """,
)
async def handle_inbound_email(
    request: Request,
    svix_signature: Annotated[Optional[str], Header(alias="svix-signature")] = None,
) -> EmailWebhookResponse:
    """
    Handle Resend inbound email webhook.
    
    Args:
        request: FastAPI request object
        svix_signature: Resend signature header
        
    Returns:
        EmailWebhookResponse with ingestion results
        
    Raises:
        HTTPException 401: Invalid signature
        HTTPException 400: Invalid payload or missing tenant
        HTTPException 429: Rate limit exceeded
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Step 1: Read raw request body for signature verification
    try:
        payload_body = await request.body()
    except (IOError, OSError, RuntimeError) as e:
        logger.error(
            "Failed to read request body",
            extra={
                "request_id": request_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_REQUEST",
                "message": "Failed to read request body",
            },
        ) from e
    except Exception as e:
        logger.error(
            "Unexpected error reading request body",
            extra={
                "request_id": request_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Unexpected error reading request",
            },
        ) from e
    
    # Step 2: Verify Resend signature
    if not RESEND_WEBHOOK_SECRET:
        logger.error("RESEND_WEBHOOK_SECRET not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "CONFIGURATION_ERROR",
                "message": "Webhook secret not configured",
            },
        )
    
    verifier = ResendVerifier(RESEND_WEBHOOK_SECRET)
    if not verifier.verify_signature(payload_body, svix_signature):
        logger.warning(
            "Invalid Resend signature",
            extra={"request_id": request_id},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_SIGNATURE",
                "message": "Invalid webhook signature",
            },
        )
    
    # Step 3: Parse JSON payload (from already-read body)
    try:
        import json
        payload = json.loads(payload_body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(
            "Failed to parse JSON payload",
            extra={"request_id": request_id, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_PAYLOAD",
                "message": "Invalid JSON payload",
            },
        )
    
    # Step 4: Extract tenant slug from recipient
    to_address = payload.get("to") or ""
    tenant_slug = extract_tenant_slug(to_address)
    
    if not tenant_slug:
        logger.warning(
            "Could not extract tenant slug from recipient",
            extra={
                "request_id": request_id,
                "to_address_hash": hash_email(to_address),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_RECIPIENT",
                "message": f"Recipient address must match pattern: {{slug}}@{EMAIL_INGEST_DOMAIN}",
            },
        )
    
    # Step 5: Get tenant ID from slug
    supabase = get_service_client()
    tenant_id = await get_tenant_id_by_slug(supabase, tenant_slug)
    
    if not tenant_id:
        logger.warning(
            "Tenant not found",
            extra={
                "request_id": request_id,
                "tenant_slug": tenant_slug,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "TENANT_NOT_FOUND",
                "message": f"Tenant with slug '{tenant_slug}' not found",
            },
        )
    
    # Step 6: Parse email
    try:
        parser = EmailParser()
        parsed_email = parser.parse_resend_webhook(payload)
    except (ValueError, KeyError, TypeError) as e:
        logger.error(
            "Failed to parse email - invalid payload structure",
            extra={
                "request_id": request_id,
                "tenant_slug": tenant_slug,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "PARSE_ERROR",
                "message": "Failed to parse email content",
            },
        ) from e
    except Exception as e:
        logger.error(
            "Unexpected error parsing email",
            extra={
                "request_id": request_id,
                "tenant_slug": tenant_slug,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Unexpected error parsing email",
            },
        ) from e
    
    # Step 7: Check rate limit
    try:
        rate_limiter = EmailRateLimiter(supabase)
        rate_limiter.check_rate_limit(parsed_email.from_address)
    except RateLimitError as e:
        logger.warning(
            "Email rate limit exceeded",
            extra={
                "request_id": request_id,
                "tenant_slug": tenant_slug,
                "from_address_hash": hash_email(parsed_email.from_address),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "RATE_LIMIT_ERROR",
                "message": e.message,
                "retry_after": e.retry_after,
            },
        )
    
    # Step 8: Ingest email
    try:
        ingestion_service = EmailIngestionService(supabase)
        result = ingestion_service.ingest_email(
            parsed_email=parsed_email,
            tenant_id=tenant_id,
        )
        
        logger.info(
            "Email ingested successfully",
            extra={
                "request_id": request_id,
                "tenant_slug": tenant_slug,
                "email_ingestion_id": result["email_ingestion_id"],
            },
        )
        
        return EmailWebhookResponse(
            success=True,
            message="Email ingested successfully",
            email_ingestion_id=result["email_ingestion_id"],
        )
    
    except ValidationError as e:
        logger.warning(
            "Email validation failed",
            extra={
                "request_id": request_id,
                "tenant_slug": tenant_slug,
                "error": e.message,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": e.message,
                "details": e.details,
            },
        )
    
    except NotFoundError as e:
        logger.warning(
            "Resource not found during ingestion",
            extra={
                "request_id": request_id,
                "tenant_slug": tenant_slug,
                "error": e.message,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": e.message,
            },
        )
    
    except Exception as e:
        logger.error(
            "Unexpected error ingesting email",
            extra={
                "request_id": request_id,
                "tenant_slug": tenant_slug,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INGESTION_ERROR",
                "message": "Failed to ingest email",
            },
        )


def extract_tenant_slug(to_address: str) -> Optional[str]:
    """
    Extract tenant slug from recipient email address.
    
    Expected format: {slug}@<EMAIL_INGEST_DOMAIN>
    
    Args:
        to_address: Recipient email address
        
    Returns:
        Tenant slug or None if pattern doesn't match
    """
    if not to_address:
        return None
    
    # Extract email address (handle "Name <email>" format)
    from src.services.email_parser import EmailParser
    parser = EmailParser()
    clean_address = parser._extract_address(to_address)
    
    # Parse domain
    if "@" not in clean_address:
        return None
    
    local_part, domain = clean_address.split("@", 1)
    
    # Check if domain matches ingest pattern
    if domain != EMAIL_INGEST_DOMAIN:
        return None
    
    # Return slug (local part)
    return local_part.strip() if local_part else None


async def get_tenant_id_by_slug(supabase: Client, slug: str) -> Optional[UUID]:
    """
    Get tenant ID by slug.
    
    Only returns tenants with status 'active' to prevent ingestion into
    inactive or suspended accounts.
    
    Args:
        supabase: Supabase client
        slug: Tenant slug
        
    Returns:
        Tenant ID or None if not found or not active
    """
    try:
        result = (
            supabase.table("tenants")
            .select("id")
            .eq("slug", slug)
            .eq("status", "active")
            .maybe_single()
            .execute()
        )
        
        if result.data:
            return UUID(result.data["id"])
        
        return None
    except Exception as e:
        logger.error(
            "Unexpected error fetching tenant by slug",
            extra={
                "slug": slug,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        return None
