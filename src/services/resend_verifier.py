"""
Resend Webhook Signature Verifier - Ingestion Plane

Verifies Resend webhook signatures using HMAC-SHA256.
"""

import base64
import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


class ResendVerifier:
    """Service for verifying Resend webhook signatures."""

    def __init__(self, webhook_secret: str):
        """
        Initialize Resend verifier.

        Args:
            webhook_secret: Resend webhook signing secret (may include 'whsec_' prefix)
        """
        if not webhook_secret:
            raise ValueError("Resend webhook secret is required")
        # Strip 'whsec_' prefix if present (Svix format)
        if webhook_secret.startswith("whsec_"):
            self.webhook_secret = webhook_secret[6:]  # Remove 'whsec_' prefix
        else:
            self.webhook_secret = webhook_secret

    def verify_signature(
        self,
        payload_body: bytes,
        signature_header: str | None,
    ) -> bool:
        """
        Verify Resend webhook signature.

        Resend uses HMAC-SHA256 with the webhook secret to sign the raw request body.
        The signature is provided in the 'svix-signature' header.

        Args:
            payload_body: Raw request body bytes
            signature_header: Value of 'svix-signature' header (format: "v1,<signature>")

        Returns:
            True if signature is valid, False otherwise
        """
        if not signature_header:
            logger.warning("Missing Resend signature header")
            return False

        try:
            # Parse signature header (format: "v1,<base64_signature>")
            parts = signature_header.split(",")
            if len(parts) != 2 or parts[0] != "v1":
                logger.warning(f"Invalid signature header format: {signature_header}")
                return False

            received_signature_b64 = parts[1].strip()

            # Compute expected signature (Svix uses base64-encoded HMAC-SHA256)
            expected_signature = hmac.new(
                self.webhook_secret.encode("utf-8"),
                payload_body,
                hashlib.sha256,
            ).digest()
            expected_signature_b64 = base64.b64encode(expected_signature).decode("utf-8")

            # Compare signatures (constant-time comparison)
            is_valid = hmac.compare_digest(
                received_signature_b64,
                expected_signature_b64,
            )

            if not is_valid:
                logger.warning("Resend signature verification failed")

            return is_valid

        except Exception as e:
            logger.error(
                "Error during signature verification",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False
