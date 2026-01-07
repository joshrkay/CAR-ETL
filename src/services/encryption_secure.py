"""Secure encryption utilities for CAR Platform using AES-256-GCM.

SECURITY IMPROVEMENTS:
- Removed PBKDF2 fallback with hardcoded salt
- Requires base64-encoded keys only
- Improved key validation
- Optional AAD support for metadata
"""
import os
import base64
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EncryptionService:
    """Service for encrypting and decrypting sensitive data using AES-256-GCM.
    
    SECURITY NOTES:
    - Requires base64-encoded 32-byte (256-bit) keys
    - Uses AES-256-GCM for authenticated encryption
    - Generates unique nonce for each encryption
    - Supports optional AAD (Authenticated Additional Data)
    """
    
    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize encryption service.
        
        Args:
            encryption_key: Base64-encoded 32-byte encryption key. If not provided,
                          reads from ENCRYPTION_KEY environment variable.
        
        Raises:
            ValueError: If encryption key is not provided, invalid format, or wrong length.
        """
        key_str = encryption_key or os.getenv("ENCRYPTION_KEY")
        
        if not key_str:
            raise ValueError(
                "ENCRYPTION_KEY environment variable is required. "
                "Generate with: python scripts/generate_encryption_key.py"
            )
        
        # SECURITY: Only accept base64-encoded keys (no PBKDF2 fallback)
        try:
            # Decode base64 key
            self.key = base64.urlsafe_b64decode(key_str)
        except Exception as e:
            raise ValueError(
                f"Invalid encryption key format: {e}. "
                "Key must be base64-encoded. Generate with: python scripts/generate_encryption_key.py"
            )
        
        # SECURITY: Validate key length (must be exactly 32 bytes for AES-256)
        if len(self.key) != 32:
            raise ValueError(
                f"Encryption key must be exactly 32 bytes (256 bits) for AES-256. "
                f"Received {len(self.key)} bytes. "
                "Generate with: python scripts/generate_encryption_key.py"
            )
        
        self.aesgcm = AESGCM(self.key)
    
    def encrypt(self, plaintext: str, additional_data: Optional[bytes] = None) -> str:
        """Encrypt plaintext using AES-256-GCM.
        
        Args:
            plaintext: String to encrypt.
            additional_data: Optional authenticated additional data (AAD).
                           Can include metadata like tenant_id for additional security.
        
        Returns:
            Base64-encoded encrypted string with nonce prepended.
        
        Raises:
            ValueError: If plaintext is empty.
        """
        if not plaintext:
            raise ValueError("Plaintext cannot be empty")
        
        # SECURITY: Generate cryptographically secure random nonce
        # 12 bytes is the recommended size for GCM mode
        nonce = os.urandom(12)
        
        # Encrypt with optional AAD
        ciphertext = self.aesgcm.encrypt(
            nonce,
            plaintext.encode('utf-8'),
            additional_data  # Can be None or bytes
        )
        
        # Combine nonce + ciphertext and encode as base64
        # Format: [12-byte nonce][ciphertext]
        encrypted_data = nonce + ciphertext
        return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
    
    def decrypt(self, encrypted_data: str, additional_data: Optional[bytes] = None) -> str:
        """Decrypt encrypted data using AES-256-GCM.
        
        Args:
            encrypted_data: Base64-encoded encrypted string with nonce.
            additional_data: Optional authenticated additional data (AAD).
                           Must match the AAD used during encryption.
        
        Returns:
            Decrypted plaintext string.
        
        Raises:
            ValueError: If decryption fails, data is invalid, or AAD doesn't match.
        """
        if not encrypted_data:
            raise ValueError("Encrypted data cannot be empty")
        
        try:
            # Decode base64
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            
            # SECURITY: Validate minimum length (nonce + at least 1 byte ciphertext)
            if len(encrypted_bytes) < 13:
                raise ValueError("Invalid encrypted data format: too short")
            
            # Extract nonce (first 12 bytes) and ciphertext (rest)
            nonce = encrypted_bytes[:12]
            ciphertext = encrypted_bytes[12:]
            
            # Decrypt with optional AAD
            # GCM will raise exception if AAD doesn't match or data is tampered
            plaintext = self.aesgcm.decrypt(nonce, ciphertext, additional_data)
            return plaintext.decode('utf-8')
        
        except Exception as e:
            # SECURITY: Don't expose internal error details
            raise ValueError(f"Decryption failed: Invalid key or corrupted data")


def get_encryption_service() -> EncryptionService:
    """Get or create encryption service instance."""
    return EncryptionService()


# Backward compatibility alias (consider deprecating)
EncryptionServiceSecure = EncryptionService
