"""Test script for email ingestion webhook endpoint."""
import os
import sys
import json
import base64
import hmac
import hashlib
from pathlib import Path
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()
except ImportError:
    pass

from fastapi.testclient import TestClient
from src.main import app
from supabase import create_client, Client
from src.auth.config import get_auth_config


def create_resend_signature(payload_body: bytes, secret: str) -> str:
    """
    Create Resend webhook signature for testing.
    
    Args:
        payload_body: Raw request body bytes
        secret: Webhook secret (may include 'whsec_' prefix)
        
    Returns:
        Signature header value (format: "v1,<base64_signature>")
    """
    # Strip 'whsec_' prefix if present (Svix format)
    if secret.startswith("whsec_"):
        secret = secret[6:]
    
    signature = hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).digest()
    signature_b64 = base64.b64encode(signature).decode("utf-8")
    return f"v1,{signature_b64}"


def create_test_tenant(supabase: Client, slug: str) -> str:
    """
    Create a test tenant or return existing tenant ID.
    
    Args:
        supabase: Supabase client
        slug: Tenant slug
        
    Returns:
        Tenant ID (UUID string)
    """
    # Check if tenant exists
    try:
        result = (
            supabase.table("tenants")
            .select("id")
            .eq("slug", slug)
            .maybe_single()
            .execute()
        )
        
        if result and result.data:
            print(f"   Using existing tenant: {result.data['id']}")
            return result.data["id"]
    except Exception as e:
        print(f"   Warning: Error checking for existing tenant: {e}")
    
    # Create new tenant
    try:
        result = (
            supabase.table("tenants")
            .insert({
                "slug": slug,
                "name": f"Test Tenant {slug}",
                "status": "active",
            })
            .execute()
        )
        
        if not result or not result.data:
            raise Exception("Failed to create tenant - no data returned")
        
        tenant_id = result.data[0]["id"]
        print(f"   Created new tenant: {tenant_id}")
        return tenant_id
    except Exception as e:
        print(f"   Error creating tenant: {e}")
        raise Exception(f"Failed to create tenant: {str(e)}")


def test_email_webhook():
    """Test the email webhook endpoint."""
    # Check for required environment variables
    required_vars = [
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "RESEND_WEBHOOK_SECRET",
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set them in .env file or environment variables")
        return False
    
    try:
        config = get_auth_config()
    except Exception as e:
        print(f"ERROR: Failed to load auth config: {e}")
        print("Please ensure all Supabase environment variables are set")
        return False
    
    # Initialize Supabase client
    supabase: Client = create_client(
        config.supabase_url,
        config.supabase_service_key,
    )
    
    # Get webhook secret
    webhook_secret = os.getenv("RESEND_WEBHOOK_SECRET")
    
    print("=" * 60)
    print("Testing Email Ingestion Webhook")
    print("=" * 60)
    
    # Step 1: Create test tenant
    print("\n1. Setting up test tenant...")
    tenant_slug = f"test-{uuid4().hex[:8]}"
    tenant_id = create_test_tenant(supabase, tenant_slug)
    print(f"   Tenant slug: {tenant_slug}")
    print(f"   Tenant ID: {tenant_id}")
    
    # Step 2: Create test email payload
    print("\n2. Creating test email payload...")
    email_payload = {
        "from": "sender@example.com",
        "to": f"{tenant_slug}@ingest.yourapp.com",
        "subject": "Test Email - Email Ingestion",
        "text": "This is a test email body for ingestion testing.",
        "html": "<p>This is a test email body for ingestion testing.</p>",
        "attachments": [],
    }
    
    # Step 3: Create signature
    print("\n3. Creating webhook signature...")
    payload_body = json.dumps(email_payload).encode("utf-8")
    signature = create_resend_signature(payload_body, webhook_secret)
    print(f"   Signature created: {signature[:20]}...")
    
    # Step 4: Test webhook endpoint
    print("\n4. Testing webhook endpoint...")
    client = TestClient(app)
    
    # Use content= instead of json= to send raw bytes for signature verification
    response = client.post(
        "/api/v1/webhooks/email/inbound",
        content=payload_body,
        headers={
            "svix-signature": signature,
            "Content-Type": "application/json",
        },
    )
    
    print(f"   Status Code: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        result = response.json()
        print("\n[PASSED] Webhook test PASSED")
        print(f"   Email Ingestion ID: {result.get('email_ingestion_id')}")
        
        # Step 5: Verify email ingestion record
        print("\n5. Verifying email ingestion record...")
        if result.get("email_ingestion_id"):
            ingestion_id = result["email_ingestion_id"]
            ingestion_result = (
                supabase.table("email_ingestions")
                .select("*")
                .eq("id", ingestion_id)
                .maybe_single()
                .execute()
            )
            
            if ingestion_result.data:
                print("   [OK] Email ingestion record found")
                print(f"   From: {ingestion_result.data['from_address']}")
                print(f"   To: {ingestion_result.data['to_address']}")
                print(f"   Subject: {ingestion_result.data['subject']}")
                print(f"   Attachment Count: {ingestion_result.data['attachment_count']}")
                
                # Check if body document was created
                if ingestion_result.data.get("body_document_id"):
                    body_doc_id = ingestion_result.data["body_document_id"]
                    doc_result = (
                        supabase.table("documents")
                        .select("*")
                        .eq("id", body_doc_id)
                        .maybe_single()
                        .execute()
                    )
                    
                    if doc_result.data:
                        print(f"   [OK] Body document created: {body_doc_id}")
                        print(f"   Document status: {doc_result.data['status']}")
                        print(f"   Source type: {doc_result.data['source_type']}")
                    else:
                        print(f"   [WARNING] Body document not found: {body_doc_id}")
            else:
                print("   [WARNING] Email ingestion record not found")
        
        return True
    else:
        print("\n[FAILED] Webhook test FAILED")
        print(f"   Error: {response.json()}")
        return False


def test_email_webhook_with_attachment():
    """Test webhook with email attachment."""
    # Check for required environment variables
    required_vars = [
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "RESEND_WEBHOOK_SECRET",
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    try:
        config = get_auth_config()
    except Exception as e:
        print(f"ERROR: Failed to load auth config: {e}")
        return False
    
    supabase: Client = create_client(
        config.supabase_url,
        config.supabase_service_key,
    )
    
    webhook_secret = os.getenv("RESEND_WEBHOOK_SECRET")
    
    print("\n" + "=" * 60)
    print("Testing Email Webhook with Attachment")
    print("=" * 60)
    
    # Create test tenant
    print("\n1. Setting up test tenant...")
    tenant_slug = f"test-{uuid4().hex[:8]}"
    tenant_id = create_test_tenant(supabase, tenant_slug)
    
    # Create test PDF content
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 0\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    pdf_b64 = base64.b64encode(pdf_content).decode("utf-8")
    
    # Create email payload with attachment
    print("\n2. Creating test email with attachment...")
    email_payload = {
        "from": "sender@example.com",
        "to": f"{tenant_slug}@ingest.yourapp.com",
        "subject": "Test Email with Attachment",
        "text": "This email contains a PDF attachment.",
        "html": "<p>This email contains a PDF attachment.</p>",
        "attachments": [
            {
                "filename": "test-document.pdf",
                "content_type": "application/pdf",
                "content": pdf_b64,
            }
        ],
    }
    
    # Create signature
    print("\n3. Creating webhook signature...")
    payload_body = json.dumps(email_payload).encode("utf-8")
    signature = create_resend_signature(payload_body, webhook_secret)
    
    # Test webhook
    print("\n4. Testing webhook endpoint...")
    client = TestClient(app)
    
    # Use content= instead of json= to send raw bytes for signature verification
    response = client.post(
        "/api/v1/webhooks/email/inbound",
        content=payload_body,
        headers={
            "svix-signature": signature,
            "Content-Type": "application/json",
        },
    )
    
    print(f"   Status Code: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        result = response.json()
        print("\n[PASSED] Webhook with attachment test PASSED")
        
        # Verify attachment document was created
        if result.get("email_ingestion_id"):
            ingestion_result = (
                supabase.table("email_ingestions")
                .select("*")
                .eq("id", result["email_ingestion_id"])
                .maybe_single()
                .execute()
            )
            
            if ingestion_result.data:
                attachment_count = ingestion_result.data.get("attachment_count", 0)
                print(f"   Attachment count: {attachment_count}")
                
                if attachment_count > 0:
                    print("   [OK] Attachment document created")
                else:
                    print("   [WARNING] No attachments processed")
        
        return True
    else:
        print("\n[FAILED] Webhook with attachment test FAILED")
        return False


def test_invalid_signature():
    """Test webhook with invalid signature."""
    print("\n" + "=" * 60)
    print("Testing Invalid Signature Rejection")
    print("=" * 60)
    
    email_payload = {
        "from": "sender@example.com",
        "to": "test@ingest.yourapp.com",
        "subject": "Test",
        "text": "Test body",
    }
    
    client = TestClient(app)
    
    # Test with invalid signature
    response = client.post(
        "/api/v1/webhooks/email/inbound",
        json=email_payload,
        headers={
            "svix-signature": "v1,invalid_signature_here",
            "Content-Type": "application/json",
        },
    )
    
    print(f"   Status Code: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 401:
        print("\n[PASSED] Invalid signature correctly rejected")
        return True
    else:
        print("\n[FAILED] Invalid signature not rejected")
        return False


def test_invalid_recipient():
    """Test webhook with invalid recipient format."""
    print("\n" + "=" * 60)
    print("Testing Invalid Recipient Format")
    print("=" * 60)
    
    webhook_secret = os.getenv("RESEND_WEBHOOK_SECRET")
    if not webhook_secret:
        print("ERROR: RESEND_WEBHOOK_SECRET not set")
        print("Skipping test - requires webhook secret for signature generation")
        return False
    
    # Use a valid signature but invalid recipient format
    # This tests that signature passes but recipient validation fails
    email_payload = {
        "from": "sender@example.com",
        "to": "invalid-email-format",  # Not matching {slug}@ingest.yourapp.com
        "subject": "Test",
        "text": "Test body",
    }
    
    payload_body = json.dumps(email_payload).encode("utf-8")
    signature = create_resend_signature(payload_body, webhook_secret)
    
    client = TestClient(app)
    
    # Use content= instead of json= to send raw bytes for signature verification
    response = client.post(
        "/api/v1/webhooks/email/inbound",
        content=payload_body,
        headers={
            "svix-signature": signature,
            "Content-Type": "application/json",
        },
    )
    
    print(f"   Status Code: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    
    # Should get 400 for invalid recipient (signature is valid, but recipient format is wrong)
    # OR 404 if tenant not found (which is also acceptable)
    if response.status_code in [400, 404]:
        print("\n[PASSED] Invalid recipient correctly rejected")
        return True
    else:
        print(f"\n[FAILED] Invalid recipient not rejected (got {response.status_code}, expected 400 or 404)")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Email Webhook Test Suite")
    print("=" * 60)
    
    results = []
    
    # Test 1: Basic webhook
    try:
        results.append(("Basic Webhook", test_email_webhook()))
    except Exception as e:
        print(f"\n[FAILED] Basic webhook test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Basic Webhook", False))
    
    # Test 2: Webhook with attachment
    try:
        results.append(("Webhook with Attachment", test_email_webhook_with_attachment()))
    except Exception as e:
        print(f"\n[FAILED] Attachment test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Webhook with Attachment", False))
    
    # Test 3: Invalid signature
    try:
        results.append(("Invalid Signature", test_invalid_signature()))
    except Exception as e:
        print(f"\n[FAILED] Invalid signature test failed with exception: {e}")
        results.append(("Invalid Signature", False))
    
    # Test 4: Invalid recipient
    try:
        results.append(("Invalid Recipient", test_invalid_recipient()))
    except Exception as e:
        print(f"\n[FAILED] Invalid recipient test failed with exception: {e}")
        results.append(("Invalid Recipient", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "[PASSED]" if passed else "[FAILED]"
        print(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n[SUCCESS] All tests passed!")
        sys.exit(0)
    else:
        print("\n[WARNING] Some tests failed")
        sys.exit(1)
