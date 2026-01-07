"""Generate encryption key for ENCRYPTION_KEY environment variable."""
import secrets
import base64

def generate_encryption_key() -> str:
    """Generate a secure 32-byte (256-bit) encryption key.
    
    Returns:
        Base64-encoded encryption key suitable for AES-256-GCM.
    """
    # Generate 32 random bytes (256 bits)
    key_bytes = secrets.token_bytes(32)
    
    # Encode as base64 URL-safe string
    key_b64 = base64.urlsafe_b64encode(key_bytes).decode('utf-8')
    
    return key_b64


if __name__ == "__main__":
    key = generate_encryption_key()
    print("=" * 60)
    print("Encryption Key Generated")
    print("=" * 60)
    print()
    print("Set this as your ENCRYPTION_KEY environment variable:")
    print()
    print(f"  $env:ENCRYPTION_KEY=\"{key}\"")
    print()
    print("Or add to your .env file:")
    print(f"  ENCRYPTION_KEY={key}")
    print()
    print("=" * 60)
    print("⚠️  Keep this key secret! Do not commit it to version control.")
    print("=" * 60)
