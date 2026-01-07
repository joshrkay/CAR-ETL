# Role-Based Access Control (RBAC) - Access Patterns

## Overview

This document describes the role-based access patterns implemented across all API endpoints in the CAR Platform.

---

## Roles and Permissions

### Admin Role
- **Full Access:** All operations across the platform
- **Permissions:**
  - User Management (create, delete, update, list)
  - Tenant Management (modify, view)
  - Billing (access, view)
  - Document Operations (upload, edit, delete, view, search)
  - AI Operations (override decisions, train models)
  - System Administration

### Analyst Role
- **Document Operations:** Full CRUD on documents
- **AI Operations:** Can override AI decisions
- **Read-Only Tenant Settings:** Can view but not modify
- **Permissions:**
  - Document Operations (upload, edit, delete, view, search)
  - AI Operations (override decisions)
  - Tenant Settings (view only)
- **Restricted:**
  - ❌ User Management
  - ❌ Tenant Provisioning
  - ❌ Billing Access
  - ❌ Modify Tenant Settings

### Viewer Role
- **Read-Only Access:** Can view documents and search
- **Permissions:**
  - Document Operations (view, search)
  - Tenant Settings (view only)
- **Restricted:**
  - ❌ All write operations
  - ❌ User Management
  - ❌ Tenant Provisioning
  - ❌ Billing Access
  - ❌ AI Operations

---

## Endpoint Access Matrix

### Tenant Provisioning (`/api/v1/tenants`)

| Endpoint | Admin | Analyst | Viewer |
|----------|-------|---------|--------|
| `POST /api/v1/tenants` | ✅ | ❌ | ❌ |

**Protection:** `Depends(require_role("admin"))`

---

### User Management (`/api/v1/rbac-examples/users`)

| Endpoint | Admin | Analyst | Viewer |
|----------|-------|---------|--------|
| `POST /api/v1/rbac-examples/users` | ✅ | ❌ | ❌ |
| `GET /api/v1/rbac-examples/users` | ✅ | ❌ | ❌ |
| `DELETE /api/v1/rbac-examples/users/{user_id}` | ✅ | ❌ | ❌ |

**Protection:** `@requires_role("Admin")`

---

### Tenant Settings (`/api/v1/rbac-examples/tenant/settings`)

| Endpoint | Admin | Analyst | Viewer |
|----------|-------|---------|--------|
| `PATCH /api/v1/rbac-examples/tenant/settings` | ✅ | ❌ | ❌ |
| `GET /api/v1/rbac-examples/tenant/settings` | ✅ | ✅ | ✅ |

**Protection:**
- Modify: `@requires_role("Admin")`
- View: `@requires_permission("view_tenant_settings")`

---

### Billing (`/api/v1/rbac-examples/billing`)

| Endpoint | Admin | Analyst | Viewer |
|----------|-------|---------|--------|
| `GET /api/v1/rbac-examples/billing` | ✅ | ❌ | ❌ |

**Protection:** `@requires_role("Admin")`

---

### Document Operations (`/api/v1/rbac-examples/documents`)

| Endpoint | Admin | Analyst | Viewer |
|----------|-------|---------|--------|
| `POST /api/v1/rbac-examples/documents` | ✅ | ✅ | ❌ |
| `PUT /api/v1/rbac-examples/documents/{document_id}` | ✅ | ✅ | ❌ |
| `DELETE /api/v1/rbac-examples/documents/{document_id}` | ✅ | ✅ | ❌ |
| `GET /api/v1/rbac-examples/documents/{document_id}` | ✅ | ✅ | ✅ |
| `GET /api/v1/rbac-examples/documents/search` | ✅ | ✅ | ✅ |
| `GET /api/v1/rbac-examples/documents` | ✅ | ✅ | ✅ |

**Protection:**
- Upload: `@requires_permission("upload_document")`
- Edit: `@requires_permission("edit_document")`
- Delete: `@requires_permission("delete_document")`
- View: `@requires_permission("view_document")`
- Search: `@requires_permission("search_documents")`
- List: `@requires_role("Viewer", "Analyst", "Admin")`

---

### AI Operations (`/api/v1/rbac-examples/ai/override`)

| Endpoint | Admin | Analyst | Viewer |
|----------|-------|---------|--------|
| `POST /api/v1/rbac-examples/ai/override` | ✅ | ✅ | ❌ |

**Protection:** `@requires_permission("override_ai_decision")`

---

## Example Endpoints

### JWT Usage Examples (`/api/v1/example`)

| Endpoint | Admin | Analyst | Viewer |
|----------|-------|---------|--------|
| `GET /api/v1/example/me` | ✅ | ✅ | ✅ |
| `GET /api/v1/example/admin-only` | ✅ | ❌ | ❌ |
| `GET /api/v1/example/tenant-data` | ✅ | ✅ | ✅ |
| `GET /api/v1/example/moderator-or-admin` | ✅ | ✅ | ❌ |

**Protection:**
- `/me`: `@requires_permission("view_tenant_settings")`
- `/admin-only`: `@requires_role("Admin")`
- `/tenant-data`: `@requires_permission("view_document")`
- `/moderator-or-admin`: `@requires_any_role(["Admin", "Analyst"])`

### Tenant Context Examples (`/api/v1/example`)

| Endpoint | Admin | Analyst | Viewer |
|----------|-------|---------|--------|
| `GET /api/v1/example/tenant-info` | ✅ | ✅ | ✅ |
| `GET /api/v1/example/tenant-data` | ✅ | ✅ | ✅ |

**Protection:**
- `/tenant-info`: `@requires_permission("view_tenant_settings")`
- `/tenant-data`: `@requires_permission("view_document")`

---

## Access Pattern Summary

### Admin Access Pattern
```
✅ All endpoints accessible
✅ Full CRUD on all resources
✅ User and tenant management
✅ Billing access
✅ System administration
```

### Analyst Access Pattern
```
✅ Document CRUD operations
✅ AI decision override
✅ View tenant settings
❌ User management
❌ Tenant provisioning
❌ Billing access
❌ Modify tenant settings
```

### Viewer Access Pattern
```
✅ View documents
✅ Search documents
✅ View tenant settings
❌ All write operations
❌ User management
❌ Tenant provisioning
❌ Billing access
❌ AI operations
```

---

## Implementation Details

### Decorator-Based Protection
Most endpoints use decorator-based RBAC:
```python
@router.post("/endpoint")
@requires_role("Admin")
async def endpoint(claims: JWTClaims = Depends(get_current_user_claims)):
    ...
```

### Dependency-Based Protection
Some endpoints (e.g., rate-limited) use dependency-based RBAC:
```python
@router.post("/endpoint")
async def endpoint(claims: JWTClaims = Depends(require_role("admin"))):
    ...
```

### Permission-Based Protection
Granular permission checks:
```python
@router.post("/endpoint")
@requires_permission("upload_document")
async def endpoint(claims: JWTClaims = Depends(get_current_user_claims)):
    ...
```

---

## Security Features

1. **JWT Validation:** All protected endpoints require valid JWT tokens
2. **Role-Based Access:** Admin, Analyst, Viewer roles enforced
3. **Permission-Based Access:** Granular permission checks
4. **Audit Logging:** All access denials logged
5. **Request Caching:** Role checks cached per request
6. **Case-Insensitive:** Role names normalized

---

## Error Responses

### 401 Unauthorized
- Missing or invalid JWT token
- Expired token
- Missing tenant_id claim

### 403 Forbidden
- User lacks required role
- User lacks required permission
- Inactive tenant

---

## Testing

To test role access patterns:

1. **Unit Tests:** `tests/test_role_access_patterns.py`
2. **Integration Tests:** Requires environment variables:
   - `ENCRYPTION_KEY`
   - `AUTH0_DOMAIN`
   - `AUTH0_MANAGEMENT_CLIENT_ID`
   - `AUTH0_MANAGEMENT_CLIENT_SECRET`
   - `AUTH0_DATABASE_CONNECTION_NAME`

**Note:** Full integration tests require proper environment setup. The RBAC decorators and dependencies are tested in isolation in `tests/test_rbac.py` and `tests/test_rbac_decorators.py`.

---

## Files Modified

1. ✅ `src/api/routes/tenants.py` - Admin role protection
2. ✅ `src/api/routes/rbac_examples.py` - All endpoints protected
3. ✅ `src/api/routes/example_jwt_usage.py` - Decorators applied
4. ✅ `src/api/routes/example_tenant_usage.py` - Permission decorators
5. ✅ `src/api/main.py` - All routers included

---

**Status:** ✅ **ALL ENDPOINTS PROTECTED WITH RBAC**
