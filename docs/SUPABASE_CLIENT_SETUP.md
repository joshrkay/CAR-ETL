# Supabase Client Library Setup

The Supabase client library is now set up for API operations in the CAR Platform.

## Installation

Install the Supabase Python client:

```bash
pip install supabase
```

Or install all dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

The Supabase client uses the configuration from `src/config/supabase_config.py`:

- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_ANON_KEY` - Public/anonymous key (for client-side)
- `SUPABASE_SERVICE_ROLE_KEY` - Secret key (for server-side admin access)

These are already configured via environment variables.

## Usage

### Basic Usage

```python
from src.db.supabase_client import get_supabase_table, get_supabase_client

# Get a table reference (using service role for admin access)
table = get_supabase_table("your_table", use_service_role=True)

# Query data
result = table.select("*").limit(10).execute()
print(result.data)

# Insert data
new_data = {"name": "example", "value": "test"}
result = table.insert(new_data).execute()
print(result.data)

# Update data
result = table.update({"value": "updated"}).eq("id", 1).execute()

# Delete data
result = table.delete().eq("id", 1).execute()
```

### Using Client Directly

```python
from src.db.supabase_client import get_supabase_client

# Get client instance
client = get_supabase_client(use_service_role=True)

# Access different features
auth = client.auth          # Authentication
storage = client.storage    # File storage
functions = client.functions  # Edge functions
table = client.table("your_table")  # Database tables
```

### Anon Key vs Service Role Key

**Anon Key (use_service_role=False):**
- Subject to Row Level Security (RLS) policies
- Use for client-side operations
- Limited by RLS rules

**Service Role Key (use_service_role=True):**
- Bypasses RLS policies
- Full admin access
- Use for server-side/admin operations
- **Keep secret!**

## Control Plane Schema

**Important:** Supabase client library accesses tables in the `public` schema by default.

For the `control_plane` schema tables:
- Option 1: Use direct PostgreSQL connection (SQLAlchemy)
- Option 2: Configure Supabase to expose `control_plane` schema
- Option 3: Use Supabase REST API with custom queries

### Using SQLAlchemy for Control Plane

For control plane operations, use the SQLAlchemy models:

```python
from src.db.connection import get_connection_manager
from src.db.models.control_plane import Tenant

manager = get_connection_manager()
with manager.get_session() as session:
    tenant = session.query(Tenant).filter_by(name="system_admin").first()
    print(tenant)
```

## Examples

See `scripts/example_supabase_usage.py` for complete examples.

## Testing

Test the Supabase client setup:

```bash
python scripts/test_supabase_client.py
```

## API Reference

### Functions

- `get_supabase_client(use_service_role=False)` - Get Supabase client instance
- `get_supabase_table(table_name, use_service_role=False)` - Get table reference

### Classes

- `SupabaseClientManager` - Manages client instances
  - `client` - Supabase client instance
  - `get_table(table_name)` - Get table reference
  - `health_check()` - Check connection health

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use anon key** for client-side operations
3. **Use service role key** only on server-side
4. **Set up RLS policies** in Supabase for data protection
5. **Rotate keys** if exposed

## Troubleshooting

### Import Error: "supabase library not installed"

```bash
pip install supabase
```

### 401 Unauthorized

- Check if you're using the correct key (anon vs service role)
- Verify RLS policies allow access
- For admin operations, use service role key

### Table Not Found

- Supabase client accesses `public` schema by default
- For `control_plane` schema, use SQLAlchemy models instead
- Or configure Supabase to expose the schema

## Next Steps

1. **Set up RLS policies** in Supabase dashboard for your tables
2. **Create tables** in Supabase (or use existing control_plane schema)
3. **Use Supabase client** for public schema operations
4. **Use SQLAlchemy** for control_plane schema operations
