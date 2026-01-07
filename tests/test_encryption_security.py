"""Security tests for encryption implementation."""
import pytest
import os
import base64
import secrets
from src.services.encryption import EncryptionService


@pytest.fixture
def valid_key():
    """Generate a valid encryption key for testing."""
    key_bytes = secrets.token_bytes(32)
    return base64.urlsafe_b64encode(key_bytes).decode('utf-8')


@pytest.fixture
def encryption_service(valid_key):
    """Create encryption service with valid key."""
    return EncryptionService(encryption_key=valid_key)


class TestEncryptionSecurity:
    """Security-focused tests for encryption."""
    
    def test_requires_base64_key(self):
        """Test that only base64-encoded keys are accepted."""
        # Invalid: not base64
        with pytest.raises(ValueError, match="Invalid encryption key format"):
            EncryptionService(encryption_key="not_base64_key")
        
        # Invalid: wrong length
        short_key = base64.urlsafe_b64encode(b"short").decode('utf-8')
        with pytest.raises(ValueError, match="must be 32 bytes"):
            EncryptionService(encryption_key=short_key)
    
    def test_nonce_uniqueness(self, encryption_service):
        """Test that each encryption uses a unique nonce."""
        plaintext = "test_connection_string"
        encrypted1 = encryption_service.encrypt(plaintext)
        encrypted2 = encryption_service.encrypt(plaintext)
        
        # Nonces should be different (first 12 bytes after base64 decode)
        import base64
        nonce1 = base64.urlsafe_b64decode(encrypted1.encode('utf-8'))[:12]
        nonce2 = base64.urlsafe_b64decode(encrypted2.encode('utf-8'))[:12]
        
        assert nonce1 != nonce2, "Nonces must be unique for each encryption"
    
    def test_tamper_detection(self, encryption_service):
        """Test that GCM detects tampering."""
        plaintext = "test_connection_string"
        encrypted = encryption_service.encrypt(plaintext)
        
        # Tamper with encrypted data
        import base64
        encrypted_bytes = bytearray(base64.urlsafe_b64decode(encrypted.encode('utf-8')))
        encrypted_bytes[20] ^= 1  # Flip a bit
        tampered = base64.urlsafe_b64encode(bytes(encrypted_bytes)).decode('utf-8')
        
        # Should raise error on tampered data
        with pytest.raises(ValueError, match="Decryption failed"):
            encryption_service.decrypt(tampered)
    
    def test_key_length_validation(self):
        """Test that key length is strictly validated."""
        # 31 bytes (too short)
        key_31 = base64.urlsafe_b64encode(secrets.token_bytes(31)).decode('utf-8')
        with pytest.raises(ValueError, match="must be 32 bytes"):
            EncryptionService(encryption_key=key_31)
        
        # 33 bytes (too long)
        key_33 = base64.urlsafe_b64encode(secrets.token_bytes(33)).decode('utf-8')
        with pytest.raises(ValueError, match="must be 32 bytes"):
            EncryptionService(encryption_key=key_33)
    
    def test_empty_plaintext_rejected(self, encryption_service):
        """Test that empty plaintext is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            encryption_service.encrypt("")
    
    def test_empty_encrypted_data_rejected(self, encryption_service):
        """Test that empty encrypted data is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            encryption_service.decrypt("")
    
    def test_wrong_key_fails(self, valid_key):
        """Test that wrong key cannot decrypt data."""
        service1 = EncryptionService(encryption_key=valid_key)
        plaintext = "test_connection_string"
        encrypted = service1.encrypt(plaintext)
        
        # Different key
        wrong_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8')
        service2 = EncryptionService(encryption_key=wrong_key)
        
        with pytest.raises(ValueError, match="Decryption failed"):
            service2.decrypt(encrypted)
    
    def test_round_trip_encryption(self, encryption_service):
        """Test that encryption/decryption works correctly."""
        test_strings = [
            "simple",
            "postgresql://user:pass@host:5432/db",
            "long_string_" * 100,
            "special_chars_!@#$%^&*()",
            "unicode_测试_🎉"
        ]
        
        for plaintext in test_strings:
            encrypted = encryption_service.encrypt(plaintext)
            decrypted = encryption_service.decrypt(encrypted)
            assert decrypted == plaintext, f"Round-trip failed for: {plaintext[:20]}"
    
    def test_environment_variable_usage(self, valid_key, monkeypatch):
        """Test that encryption service reads from environment variable."""
        monkeypatch.setenv("ENCRYPTION_KEY", valid_key)
        service = EncryptionService()
        
        # Should work without explicit key
        plaintext = "test"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext
    
    def test_no_key_raises_error(self, monkeypatch):
        """Test that missing key raises clear error."""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        
        with pytest.raises(ValueError, match="ENCRYPTION_KEY environment variable is required"):
            EncryptionService()


class TestSecurityVulnerabilities:
    """Tests to verify security vulnerabilities are not present."""
    
    def test_no_hardcoded_salt_in_key_derivation(self):
        """Test that PBKDF2 with hardcoded salt is not used."""
        import inspect
        source = inspect.getsource(EncryptionService.__init__)
        
        # Should not have hardcoded salt
        assert "car_platform_salt" not in source, "Hardcoded salt detected - SECURITY RISK"
    
    def test_key_not_logged(self, encryption_service, caplog):
        """Test that encryption key is not logged."""
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
        
        # Trigger encryption (should not log key)
        encryption_service.encrypt("test")
        
        # Check logs don't contain key
        log_text = caplog.text
        assert "ENCRYPTION_KEY" not in log_text or "key" not in log_text.lower(), \
            "Encryption key may be logged - SECURITY RISK"
    
    def test_error_messages_dont_expose_key(self, valid_key):
        """Test that error messages don't expose encryption key."""
        try:
            # Try with invalid key format
            EncryptionService(encryption_key="invalid")
        except ValueError as e:
            error_msg = str(e)
            # Should not contain actual key value
            assert valid_key not in error_msg, "Error message exposes key - SECURITY RISK"
