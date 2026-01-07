"""Example usage of Supabase client library for CAR Platform."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.db.supabase_client import get_supabase_table, get_supabase_client
from src.config.supabase_config import get_supabase_config


def example_read_tenants():
    """Example: Read tenants from control_plane.tenants table."""
    print("Example: Reading tenants from control_plane.tenants")
    print("-" * 60)
    
    try:
        # Use service role key for admin access
        table = get_supabase_table("tenants", use_service_role=True)
        
        # Note: Supabase tables are in 'public' schema by default
        # For control_plane schema, you may need to use direct SQL or
        # configure Supabase to expose the schema
        
        # Example query (adjust based on your table structure)
        # result = table.select("*").execute()
        # print(f"Found {len(result.data)} tenants")
        
        print("[INFO] Table reference created")
        print("[NOTE] For control_plane schema tables, you may need to:")
        print("       1. Use direct PostgreSQL connection, or")
        print("       2. Configure Supabase to expose control_plane schema")
        
    except Exception as e:
        print(f"[ERROR] Failed to read tenants: {e}")


def example_insert_data():
    """Example: Insert data using Supabase client."""
    print("\nExample: Inserting data")
    print("-" * 60)
    
    try:
        # Use service role key for admin access
        table = get_supabase_table("your_table", use_service_role=True)
        
        # Example insert (adjust based on your table structure)
        # data = {"name": "test", "value": "example"}
        # result = table.insert(data).execute()
        # print(f"Inserted: {result.data}")
        
        print("[INFO] Table reference created")
        print("[NOTE] Replace 'your_table' with actual table name")
        
    except Exception as e:
        print(f"[ERROR] Failed to insert data: {e}")


def example_using_client_directly():
    """Example: Using Supabase client directly."""
    print("\nExample: Using client directly")
    print("-" * 60)
    
    try:
        # Get client instance
        client = get_supabase_client(use_service_role=True)
        
        # Access any Supabase feature
        # auth = client.auth
        # storage = client.storage
        # functions = client.functions
        
        print("[INFO] Client instance created")
        print("[INFO] Available features:")
        print("       - client.auth (authentication)")
        print("       - client.storage (file storage)")
        print("       - client.functions (edge functions)")
        print("       - client.table() (database tables)")
        
    except Exception as e:
        print(f"[ERROR] Failed to create client: {e}")


def main():
    """Run all examples."""
    print("=" * 60)
    print("Supabase Client Library Examples")
    print("=" * 60)
    print()
    
    # Show configuration
    config = get_supabase_config()
    print(f"Supabase URL: {config.project_url}")
    print(f"API URL: {config.api_url}")
    print()
    
    # Run examples
    example_read_tenants()
    example_insert_data()
    example_using_client_directly()
    
    print("\n" + "=" * 60)
    print("[INFO] These are examples. Adjust for your actual use case.")
    print("=" * 60)


if __name__ == "__main__":
    main()
