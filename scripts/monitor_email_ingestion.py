"""Script to monitor email ingestion in real-time."""
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

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

from src.auth.config import get_auth_config
from supabase import Client, create_client


def monitor_recent_ingestions(supabase: Client, minutes: int = 5) -> list:
    """Get recent email ingestions from the last N minutes."""
    cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)

    try:
        result = (
            supabase.table("email_ingestions")
            .select(
                "id, tenant_id, from_address, to_address, subject, "
                "attachment_count, received_at, body_document_id"
            )
            .gte("received_at", cutoff_time.isoformat())
            .order("received_at", desc=True)
            .execute()
        )

        return result.data or []
    except Exception as e:
        print(f"[ERROR] Failed to query email ingestions: {e}")
        return []


def get_tenant_slug(supabase: Client, tenant_id: str) -> str:
    """Get tenant slug from tenant ID."""
    try:
        result = (
            supabase.table("tenants")
            .select("slug, name")
            .eq("id", tenant_id)
            .maybe_single()
            .execute()
        )

        if result.data:
            return f"{result.data['slug']} ({result.data.get('name', 'N/A')})"
        return tenant_id
    except Exception:
        return tenant_id


def get_document_info(supabase: Client, document_id: str) -> dict:
    """Get document information."""
    try:
        result = (
            supabase.table("documents")
            .select("id, original_filename, mime_type, file_size_bytes, status, source_type")
            .eq("id", document_id)
            .maybe_single()
            .execute()
        )

        if result.data:
            return result.data
        return {}
    except Exception:
        return {}


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def print_ingestion_summary(ingestions: list, supabase: Client):
    """Print formatted summary of email ingestions."""
    if not ingestions:
        print("\n[INFO] No recent email ingestions found")
        return

    print(f"\n{'='*80}")
    print(f"Email Ingestion Summary ({len(ingestions)} recent ingestion(s))")
    print(f"{'='*80}\n")

    for idx, ingestion in enumerate(ingestions, 1):
        tenant_info = get_tenant_slug(supabase, ingestion["tenant_id"])
        received_at = datetime.fromisoformat(ingestion["received_at"].replace("Z", "+00:00"))
        local_time = received_at.strftime("%Y-%m-%d %H:%M:%S UTC")

        print(f"[{idx}] Email Ingestion ID: {ingestion['id']}")
        print(f"     Received: {local_time}")
        print(f"     Tenant: {tenant_info}")
        print(f"     From: {ingestion['from_address']}")
        print(f"     To: {ingestion['to_address']}")
        print(f"     Subject: {ingestion.get('subject', '(no subject)')}")
        print(f"     Attachments: {ingestion.get('attachment_count', 0)}")

        # Get body document info
        if ingestion.get("body_document_id"):
            doc_info = get_document_info(supabase, ingestion["body_document_id"])
            if doc_info:
                print("     Body Document:")
                print(f"       - ID: {doc_info['id']}")
                print(f"       - Status: {doc_info.get('status', 'N/A')}")
                print(f"       - Size: {format_size(doc_info.get('file_size_bytes', 0))}")
                print(f"       - Type: {doc_info.get('mime_type', 'N/A')}")

        # Get attachment documents
        if ingestion.get("attachment_count", 0) > 0:
            try:
                attachments = (
                    supabase.table("documents")
                    .select("id, original_filename, mime_type, file_size_bytes, status")
                    .eq("parent_id", ingestion["body_document_id"])
                    .execute()
                )

                if attachments.data:
                    print("     Attachment Documents:")
                    for att in attachments.data:
                        print(f"       - {att.get('original_filename', 'N/A')}")
                        print(f"         ID: {att['id']}, Size: {format_size(att.get('file_size_bytes', 0))}, Status: {att.get('status', 'N/A')}")
            except Exception as e:
                print(f"     [WARNING] Could not fetch attachment details: {e}")

        print()


def monitor_loop(supabase: Client, interval_seconds: int = 10, lookback_minutes: int = 5):
    """Continuously monitor email ingestions."""
    print("="*80)
    print("Email Ingestion Monitor")
    print("="*80)
    print("\nMonitoring for new email ingestions...")
    print(f"Check interval: {interval_seconds} seconds")
    print(f"Looking back: {lookback_minutes} minutes")
    print("\nPress Ctrl+C to stop\n")

    last_count = 0

    try:
        while True:
            ingestions = monitor_recent_ingestions(supabase, lookback_minutes)
            current_count = len(ingestions)

            if current_count > last_count:
                new_count = current_count - last_count
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {new_count} new email(s) ingested!")
                print_ingestion_summary(ingestions, supabase)
                last_count = current_count
            elif current_count > 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring... ({current_count} ingestion(s) in last {lookback_minutes} min)")

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\n\n[INFO] Monitoring stopped")


def main():
    """Main entry point."""
    # Check environment variables
    required_vars = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"[ERROR] Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

    try:
        config = get_auth_config()
    except Exception as e:
        print(f"[ERROR] Failed to load auth config: {e}")
        sys.exit(1)

    # Initialize Supabase client
    try:
        supabase: Client = create_client(
            config.supabase_url,
            config.supabase_service_key,
        )
        print("[OK] Connected to Supabase")
    except Exception as e:
        print(f"[ERROR] Failed to connect to Supabase: {e}")
        sys.exit(1)

    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        # Continuous monitoring mode
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        lookback = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        monitor_loop(supabase, interval, lookback)
    else:
        # One-time check
        lookback = int(sys.argv[1]) if len(sys.argv) > 1 else 5
        ingestions = monitor_recent_ingestions(supabase, lookback)
        print_ingestion_summary(ingestions, supabase)

        if ingestions:
            print(f"\n[SUCCESS] Found {len(ingestions)} email ingestion(s) in the last {lookback} minutes")
        else:
            print(f"\n[INFO] No email ingestions found in the last {lookback} minutes")
            print("\nTo monitor continuously, run:")
            print("  python scripts/monitor_email_ingestion.py --watch")


if __name__ == "__main__":
    main()
