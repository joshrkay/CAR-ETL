"""Test script to parse and validate Auth0 certificate."""
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.auth.cert_utils import get_certificate_info, extract_auth0_domain


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
    """Main function to test certificate parsing."""
    print("Testing Auth0 Certificate Parsing\n")
    
    # Parse and display certificate info
    get_certificate_info(AUTH0_CERT)
    
    # Extract domain
    domain = extract_auth0_domain(AUTH0_CERT)
    if domain:
        print(f"\n✅ Use this domain in your .env file:")
        print(f"   AUTH0_DOMAIN={domain}")
        print(f"\n✅ Test JWKS endpoint:")
        print(f"   curl https://{domain}/.well-known/jwks.json")
    else:
        print("\n❌ Could not extract domain from certificate")


if __name__ == "__main__":
    main()
