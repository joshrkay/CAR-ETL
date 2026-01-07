"""Utilities for working with Auth0 certificates."""
from typing import Optional, Dict, Any

from cryptography import x509
from cryptography.hazmat.backends import default_backend


def parse_certificate(cert_pem: str) -> Dict[str, Any]:
    """Parse X.509 certificate and extract information."""
    try:
        # Parse PEM certificate directly
        cert = x509.load_pem_x509_certificate(cert_pem.encode('utf-8'), default_backend())
        
        # Extract information
        subject = cert.subject
        issuer = cert.issuer
        
        # Get common name (CN) from subject
        cn = None
        for attr in subject:
            if attr.oid._name == 'commonName':
                cn = attr.value
                break
        
        # Get issuer CN
        issuer_cn = None
        for attr in issuer:
            if attr.oid._name == 'commonName':
                issuer_cn = attr.value
                break
        
        return {
            "subject": str(subject),
            "issuer": str(issuer),
            "common_name": cn,
            "issuer_common_name": issuer_cn,
            "not_valid_before": cert.not_valid_before.isoformat(),
            "not_valid_after": cert.not_valid_after.isoformat(),
            "serial_number": str(cert.serial_number),
            "fingerprint": cert.fingerprint(cert.signature_hash_algorithm).hex()
        }
    except Exception as e:
        raise ValueError(f"Failed to parse certificate: {e}") from e


def extract_auth0_domain(cert_pem: str) -> Optional[str]:
    """Extract Auth0 domain from certificate."""
    try:
        cert_info = parse_certificate(cert_pem)
        cn = cert_info.get("common_name")
        
        if cn and ".auth0.com" in cn:
            return cn
        return None
    except Exception:
        return None


def validate_certificate_domain(cert_pem: str, expected_domain: str) -> bool:
    """Validate that certificate matches expected Auth0 domain."""
    domain = extract_auth0_domain(cert_pem)
    if not domain:
        return False
    
    # Normalize domains (remove protocol, handle subdomains)
    expected_clean = expected_domain.replace("https://", "").replace("http://", "").strip()
    domain_clean = domain.strip()
    
    return expected_clean.lower() == domain_clean.lower()


def get_certificate_info(cert_pem: str) -> None:
    """Print formatted certificate information."""
    try:
        cert_info = parse_certificate(cert_pem)
        
        print("=" * 60)
        print("Certificate Information")
        print("=" * 60)
        print(f"Subject: {cert_info['subject']}")
        print(f"Issuer: {cert_info['issuer']}")
        print(f"Common Name: {cert_info['common_name']}")
        print(f"Valid From: {cert_info['not_valid_before']}")
        print(f"Valid Until: {cert_info['not_valid_after']}")
        print(f"Serial Number: {cert_info['serial_number']}")
        print(f"Fingerprint: {cert_info['fingerprint']}")
        
        domain = extract_auth0_domain(cert_pem)
        if domain:
            print(f"\n✅ Extracted Auth0 Domain: {domain}")
            print(f"   JWKS URI: https://{domain}/.well-known/jwks.json")
        else:
            print("\n⚠️  Could not extract Auth0 domain from certificate")
        
        print("=" * 60)
    except Exception as e:
        print(f"❌ Error parsing certificate: {e}")
