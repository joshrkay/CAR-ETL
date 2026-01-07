"""Standalone script to parse Auth0 certificate (no dependencies on main modules)."""
from cryptography import x509
from cryptography.hazmat.backends import default_backend


# Certificate provided by user
AUTH0_CERT = """-----BEGIN CERTIFICATE-----
MIIDHTCCAgWgAwIBAgIJMhaFAiV5jh1aMA0GCSqGSIb3DQEBCwUAMCwxKjAoBgNV
BAMTIWRldi1raHg4OGMzbHU3d3oyZHh4LnVzLmF1dGgwLmNvbTAeFw0yNjAxMDcw
MTI4NDNaFw0zOTA5MTYwMTI4NDNaMCwxKjAoBgNVBAMTIWRldi1raHg4OGMzbHU3
d3oyZHh4LnVzLmF1dGgwLmNvbTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoC
ggEBAO6u+jTHkkC+yCypdJD4qr2AUlZ107q0NbX/LcYweOXYdLbJV3dtVNQzz3ks
wxhdWrha3r6ZNeTxS9RaUZIz3/77W1hTAbJ9PyMhdCwzKnCFV2vu8Y7EzzqsTYcO
hbzsUvDt7GMHPBPgBBiDHRNy8Ti65EZ0cvpyOnMiP+Pu5hRZ1dyooj9hG33mIVKE
Eib69TP7MPu0Gtcdf/aUfF0SVHFU1oTU/2r72pq8Wui4WmA18Nllrdcq5ICaIBC4
DTDG/+/oRoTqTnpFaFAv2DlqYcoi+nS6b0oV7CL0yAOMRPGDfDpjaxRECcJxgWLE
gxMj1e4sMbAO2G64ohRXH1RRkTECAwEAAaNCMEAwDwYDVR0TAQH/BAUwAwEB/zAd
BgNVHQ4EFgQUN9nIV1oMHIVQQ5PioTEt19RLizYwDgYDVR0PAQH/BAQDAgKEMA0G
CSqGSIb3DQEBCwUAA4IBAQCj5gPs4cQssiNb2Xc4kzTaJ1+7NonSddSAVP/zRSKR
tmvnlco89gx9lSvK+eeA2O/BIGV3ZEZNIyF/CbRHRQQorBi+zTg2SXsX43IGpigi
WIYqFQnsrEEXVGJB3TMp3WzGzDShMcoS8dYnBxnKq2SibXfD/o+lyIqkdNSKsk2U
xAsdYoB/jAFDlDIXvE1lWfqh7qonFV6tlf9s0XGwg53MPPafoojsWUXDT27zDh4/
TEKLW20XotNyFbjlMHA/FB0YGK0/LnFb+mDI+coAb5IqxP2W8ejvysACkB0SfHSY
AMtFNzhEIyRMUCiPhmIpD+w8uyJMdHNGr6+rnHSkixqB
-----END CERTIFICATE-----"""


def main():
    """Parse and display certificate information."""
    try:
        # Parse PEM certificate
        cert = x509.load_pem_x509_certificate(AUTH0_CERT.encode('utf-8'), default_backend())
        
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
        
        print("=" * 60)
        print("Auth0 Certificate Information")
        print("=" * 60)
        print(f"Subject: {subject}")
        print(f"Issuer: {issuer}")
        print(f"Common Name (CN): {cn}")
        print(f"Issuer CN: {issuer_cn}")
        print(f"Valid From: {cert.not_valid_before_utc.isoformat()}")
        print(f"Valid Until: {cert.not_valid_after_utc.isoformat()}")
        print(f"Serial Number: {cert.serial_number}")
        
        # Calculate fingerprint
        fingerprint = cert.fingerprint(cert.signature_hash_algorithm).hex()
        print(f"Fingerprint: {fingerprint}")
        
        if cn and ".auth0.com" in cn:
            print("\n" + "=" * 60)
            print("[SUCCESS] Extracted Auth0 Domain")
            print("=" * 60)
            print(f"Domain: {cn}")
            print(f"\nUse this in your .env file:")
            print(f"  AUTH0_DOMAIN={cn}")
            print(f"\nJWKS Endpoint:")
            print(f"  https://{cn}/.well-known/jwks.json")
            print(f"\nToken Endpoint:")
            print(f"  https://{cn}/oauth/token")
            print(f"\nManagement API:")
            print(f"  https://{cn}/api/v2")
        else:
            print("\n[WARNING] Could not extract Auth0 domain from certificate")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"[ERROR] Error parsing certificate: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
