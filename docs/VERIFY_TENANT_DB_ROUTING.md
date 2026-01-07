# Verify Tenant Database Routing

## Overview

This guide explains how to verify that the tenant context middleware correctly routes requests to the correct database per tenant, ensuring data isolation.

---

## Quick Verification

### 1. Basic Verification Script

Run the comprehensive verification script:

```bash
python scripts/verify_tenant_db_routing.py
```

**What it tests:**
- ✅ Tenant resolver initialization
- ✅ Database connection resolution for each tenant
- ✅ Database name matches expected pattern (`car_{tenant_id}`)
- ✅ Tenant isolation (different tenants get different databases)
- ✅ Cache behavior (same tenant gets cached connection)
- ✅ Invalid tenant handling
- ✅ Invalid UUID format handling

### 2. Isolation Verification Script

Run the isolation verification script:

```bash
python scripts/verify_tenant_isolation.py
```

**What it tests:**
- ✅ Multiple tenants have unique databases
- ✅ Data isolation (tenants cannot access each other's data)
- ✅ Cache statistics
- ✅ Cross-tenant data access prevention

---

## Manual Verification Steps

### Step 1: Check Environment Variables

```bash
# Required environment variables
echo $DATABASE_URL
echo $ENCRYPTION_KEY
```

### Step 2: Verify Tenants Exist

```python
from src.db.connection import get_connection_manager
from src.db.models.control_plane import Tenant, TenantStatus

connection_manager = get_connection_manager()
with connection_manager.get_session() as session:
    tenants = session.query(Tenant).filter_by(status=TenantStatus.ACTIVE).all()
    for tenant in tenants:
        print(f"Tenant: {tenant.name}, ID: {tenant.tenant_id}")
```

### Step 3: Test Tenant Resolver

```python
from src.services.tenant_resolver import get_tenant_resolver
from sqlalchemy import text

resolver = get_tenant_resolver()

# Test with a tenant ID
tenant_id = "550e8400-e29b-41d4-a716-446655440000"
engine = resolver.resolve_tenant_connection(tenant_id)

if engine:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT current_database()"))
        print(f"Database: {result.scalar()}")
else:
    print("Failed to resolve tenant connection")
```

### Step 4: Test Middleware Integration

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.middleware.tenant_context import TenantContextMiddleware
from src.dependencies import get_tenant_db, get_tenant_id
from sqlalchemy import text

app = FastAPI()

@app.get("/api/v1/test")
async def test_endpoint(request):
    db = get_tenant_db(request)
    tenant_id = get_tenant_id(request)
    
    with db.connect() as conn:
        result = conn.execute(text("SELECT current_database()"))
        database = result.scalar()
    
    return {
        "tenant_id": tenant_id,
        "database": database
    }

app.add_middleware(TenantContextMiddleware)
client = TestClient(app)

# Test with JWT token
response = client.get(
    "/api/v1/test",
    headers={"Authorization": "Bearer <your-jwt-token>"}
)
print(response.json())
```

---

## Expected Results

### ✅ Successful Verification

**Tenant Resolver:**
```
[SUCCESS] Tenant resolver initialized
[SUCCESS] Found 3 active tenant(s)
[SUCCESS] Connection established
         Database: car_550e8400_e29b_41d4_a716_446655440000
[SUCCESS] Database name matches expected pattern
[SUCCESS] Tenant isolation verified
         Tenant 1 database: car_550e8400_e29b_41d4_a716_446655440000
         Tenant 2 database: car_660e8400_e29b_41d4_a716_446655440001
[SUCCESS] Cache working correctly
```

**Isolation Verification:**
```
[SUCCESS] All 3 tenants have unique databases
[SUCCESS] Data isolation verified: Tenant 1 cannot see Tenant 2's data
[SUCCESS] All tenant connections cached
```

### ❌ Common Issues

**Issue: No tenants found**
```
[WARNING] No active tenants found in database
```
**Solution:** Create tenants using the tenant provisioning API

**Issue: Failed to resolve connection**
```
[ERROR] Failed to resolve connection for tenant
```
**Solution:** 
- Check tenant exists in control plane database
- Verify tenant status is ACTIVE
- Check ENCRYPTION_KEY is set correctly
- Verify tenant has active database record

**Issue: Database name mismatch**
```
[WARNING] Database name doesn't match expected pattern
```
**Solution:** Verify tenant database naming convention matches `car_{tenant_id}`

**Issue: Isolation failure**
```
[ERROR] Tenant isolation FAILED
```
**Solution:** 
- Verify each tenant has separate database
- Check database provisioning process
- Verify connection string encryption/decryption

---

## Verification Checklist

- [ ] Environment variables set (DATABASE_URL, ENCRYPTION_KEY)
- [ ] At least 2 active tenants exist
- [ ] Each tenant resolves to unique database
- [ ] Database names match pattern `car_{tenant_id}`
- [ ] Cache working (same tenant gets same connection)
- [ ] Invalid tenants rejected correctly
- [ ] Invalid UUID format rejected correctly
- [ ] Data isolation verified (cross-tenant access prevented)

---

## Testing with Real JWT Tokens

### 1. Generate JWT Token

```bash
# Using Auth0 Management API or test script
python scripts/test_jwt_claims.py
```

### 2. Test with curl

```bash
curl -H "Authorization: Bearer <your-jwt-token>" \
     http://localhost:8000/api/v1/test-db
```

### 3. Expected Response

```json
{
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "database": "car_550e8400_e29b_41d4_a716_446655440000",
  "status": "success"
}
```

---

## Performance Verification

### Cache Performance

```python
import time
from src.services.tenant_resolver import get_tenant_resolver

resolver = get_tenant_resolver()
tenant_id = "550e8400-e29b-41d4-a716-446655440000"

# First call (cache miss)
start = time.time()
engine1 = resolver.resolve_tenant_connection(tenant_id)
elapsed1 = (time.time() - start) * 1000
print(f"Cache miss: {elapsed1:.2f}ms")

# Second call (cache hit)
start = time.time()
engine2 = resolver.resolve_tenant_connection(tenant_id)
elapsed2 = (time.time() - start) * 1000
print(f"Cache hit: {elapsed2:.2f}ms")

# Verify cache hit is much faster
assert elapsed2 < elapsed1 / 10, "Cache not working efficiently"
```

**Expected:**
- Cache miss: ~20-30ms
- Cache hit: <1ms

---

## Troubleshooting

### Problem: Script fails with import errors

**Solution:**
```bash
# Ensure you're in project root
cd /path/to/CAR-ETL

# Install dependencies
pip install -r requirements.txt
```

### Problem: No tenants found

**Solution:**
```bash
# Create test tenants using provisioning API
# Or manually insert into database
```

### Problem: Connection resolution fails

**Solution:**
1. Check DATABASE_URL is correct
2. Verify ENCRYPTION_KEY matches the one used for encryption
3. Check tenant database record exists and is ACTIVE
4. Verify connection string decryption works

### Problem: Isolation test fails

**Solution:**
1. Verify each tenant has separate database
2. Check database names are unique
3. Verify connection strings point to different databases
4. Test database connectivity manually

---

## Next Steps

After verification:
1. ✅ Deploy middleware to production
2. ✅ Monitor cache hit rates
3. ✅ Set up alerts for isolation failures
4. ✅ Regular isolation audits

---

**Status:** ✅ **VERIFICATION SCRIPTS READY**
