"""Encryption utility for sensitive data (OAuth tokens, credentials)."""
import os
import base64
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def get_encryption_key() -> bytes:
    """
    Get encryption key from environment variable or derive from JWT secret.
    
    Uses ENCRYPTION_KEY environment variable if set, otherwise derives
    a key from SUPABASE_JWT_SECRET for development.
    
    Returns:
        Fernet-compatible encryption key (32 bytes, base64-encoded)
        
    Raises:
        ValueError: If no encryption key can be derived
    """
    encryption_key_env = os.getenv("ENCRYPTION_KEY")
    
    if encryption_key_env:
        try:
            # ENCRYPTION_KEY should be base64-encoded (from Fernet.generate_key().decode())
            # Return as-is (already base64-encoded bytes string)
            return encryption_key_env.encode()
        except Exception:
            raise ValueError("ENCRYPTION_KEY must be a valid base64-encoded key")
    
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    if not jwt_secret:
        raise ValueError(
            "Either ENCRYPTION_KEY or SUPABASE_JWT_SECRET must be set"
        )
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"car_platform_encryption_salt",
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(jwt_secret.encode()))
    return key


def encrypt_value(value: str) -> str:
    """
    Encrypt a string value using Fernet symmetric encryption.
    
    Args:
        value: Plain text string to encrypt
        
    Returns:
        Base64-encoded encrypted string
        
    Raises:
        ValueError: If encryption key cannot be derived
    """
    if not value:
        return ""
    
    key = get_encryption_key()
    fernet = Fernet(key)
    encrypted = fernet.encrypt(value.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_value(encrypted_value: str) -> str:
    """
    Decrypt a base64-encoded encrypted string.
    
    Args:
        encrypted_value: Base64-encoded encrypted string
        
    Returns:
        Decrypted plain text string
        
    Raises:
        ValueError: If decryption fails or encryption key cannot be derived
    """
    if not encrypted_value:
        return ""
    
    try:
        key = get_encryption_key()
        fernet = Fernet(key)
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_value.encode())
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode()
    except Exception as e:
        raise ValueError(f"Failed to decrypt value: {str(e)}")
