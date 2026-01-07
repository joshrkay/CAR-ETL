# Role-Based Access Control (RBAC) Documentation

## Overview

CAR Platform implements Role-Based Access Control (RBAC) with three roles: **Admin**, **Analyst**, and **Viewer**. Each role has specific permissions that determine what operations a user can perform.

---

## Roles

### Admin
**Full Access** - All platform operations

**Permissions:**
- ✅ User Management (create, delete, update, list)
- ✅ Tenant Settings (modify, view)
- ✅ Billing (access, view)
- ✅ Document Operations (upload, edit, delete, view, search)
- ✅ AI Operations (override decisions, train models)
- ✅ System Administration

### Analyst
**Read/Write Documents, No User Management**

**Permissions:**
- ✅ Document Operations (upload, edit, delete, view, search)
- ✅ AI Operations (override decisions)
- ✅ Tenant Settings (view only)
- ❌ User Management (no access)
- ❌ Billing (no access)
- ❌ Tenant Settings Modification (no access)

### Viewer
**Read-Only Access**

**Permissions:**
- ✅ Document Operations (view, search)
- ✅ Tenant Settings (view only)
- ❌ Document Write Operations (no upload, edit, delete)
- ❌ User Management (no access)
- ❌ Billing (no access)
- ❌ AI Operations (no access)

---

## Usage

### Decorator-Based Protection

#### Single Role

```python
from src.auth.decorators import requires_role
from src.auth.jwt_validator import JWTClaims
from src.auth.dependencies import get_current_user_claims

@router.post("/users")
@requires_role("Admin")
async def create_user(
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Admin only endpoint."""
    return {"message": "User created"}
```

#### Multiple Roles (Any Of)

```python
from src.auth.decorators import requires_any_role

@router.post("/documents")
@requires_any_role(["Admin", "Analyst"])
async def upload_document(
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Admin or Analyst can access."""
    return {"message": "Document uploaded"}
```

#### Permission-Based

```python
from src.auth.decorators import requires_permission

@router.post("/documents")
@requires_permission("upload_document")
async def upload_document(
    claims: JWTClaims = Depends(get_current_user_claims)
):
    """Requires upload_document permission."""
    return {"message": "Document uploaded"}
```

### Dependency-Based Protection

#### Role-Based

```python
from src.auth.rbac import RequiresRole
from src.auth.roles import Role

@router.get("/admin-only")
async def admin_endpoint(
    claims: JWTClaims = Depends(RequiresRole(Role.ADMIN))
):
    """Admin only endpoint."""
    return {"message": "Admin access"}
```

#### Permission-Based

```python
from src.auth.rbac import RequiresPermission
from src.auth.roles import Permission

@router.post("/documents")
async def upload_document(
    claims: JWTClaims = Depends(RequiresPermission(Permission.UPLOAD_DOCUMENT))
):
    """Requires upload permission."""
    return {"message": "Document uploaded"}
```

---

## Features

### Case-Insensitive Role Comparison

Roles are normalized to lowercase for comparison:

```python
@requires_role("Admin")    # Works
@requires_role("admin")    # Works
@requires_role("ADMIN")    # Works
```

### Request-Scoped Caching

Role and permission checks are cached per request to improve performance:

- Cache key: `{tenant_id}:{user_id}:{roles}`
- Cache scope: Per request (cleared after request completes)
- Cache location: `request.state.rbac_cache`

### Audit Logging

All permission denials are logged for audit purposes:

```
WARNING: RBAC_PERMISSION_DENIED: user_id=auth0|123, tenant_id=550e8400-..., 
user_roles=['viewer'], denial_type=role, required=['admin'], endpoint=/api/v1/users
```

**Audit Log Fields:**
- `timestamp`: UTC timestamp
- `user_id`: Auth0 user ID
- `tenant_id`: Tenant identifier
- `user_roles`: User's roles
- `endpoint`: Endpoint path
- `denial_type`: `role`, `roles`, or `permission`
- `required`: Required role(s) or permission
- `reason`: Additional reason for denial

---

## Error Responses

### 403 Forbidden

When a user lacks required role/permission:

```json
{
  "detail": "Required role(s): admin"
}
```

or

```json
{
  "detail": "Required permission: upload_document"
}
```

### 401 Unauthorized

When JWT token is invalid or missing:

```json
{
  "detail": "Invalid or expired token"
}
```

---

## Permission Matrix

| Permission | Admin | Analyst | Viewer |
|------------|-------|---------|--------|
| CREATE_USER | ✅ | ❌ | ❌ |
| DELETE_USER | ✅ | ❌ | ❌ |
| UPDATE_USER | ✅ | ❌ | ❌ |
| LIST_USERS | ✅ | ❌ | ❌ |
| MODIFY_TENANT_SETTINGS | ✅ | ❌ | ❌ |
| VIEW_TENANT_SETTINGS | ✅ | ✅ | ✅ |
| ACCESS_BILLING | ✅ | ❌ | ❌ |
| UPLOAD_DOCUMENT | ✅ | ✅ | ❌ |
| EDIT_DOCUMENT | ✅ | ✅ | ❌ |
| DELETE_DOCUMENT | ✅ | ✅ | ❌ |
| VIEW_DOCUMENT | ✅ | ✅ | ✅ |
| SEARCH_DOCUMENTS | ✅ | ✅ | ✅ |
| OVERRIDE_AI_DECISION | ✅ | ✅ | ❌ |

---

## Implementation Files

### Core Components

1. **`src/auth/roles.py`** - Role and permission definitions
2. **`src/auth/permissions.py`** - Permission checking logic (case-insensitive)
3. **`src/auth/rbac.py`** - FastAPI dependencies with caching
4. **`src/auth/decorators.py`** - Decorator-based RBAC
5. **`src/auth/audit.py`** - Audit logging for access control

### Example Routes

- **`src/api/routes/rbac_examples.py`** - Dependency-based examples
- **`src/api/routes/rbac_examples_decorator.py`** - Decorator-based examples

### Tests

- **`tests/test_rbac.py`** - Comprehensive RBAC tests
- **`tests/test_rbac_decorators.py`** - Decorator-specific tests

---

## Best Practices

1. **Use Decorators for Simplicity**: Prefer `@requires_role()` for simple role checks
2. **Use Dependencies for Flexibility**: Use `RequiresRole()` when you need more control
3. **Use Permissions for Granularity**: Use `@requires_permission()` for fine-grained control
4. **Always Include Claims**: Ensure `JWTClaims` is injected via `Depends(get_current_user_claims)`
5. **Log Access Denials**: All denials are automatically logged for audit

---

## Testing

### Run Tests

```bash
pytest tests/test_rbac.py -v
pytest tests/test_rbac_decorators.py -v
```

### Test Coverage

- ✅ Role definitions and permissions
- ✅ Case-insensitive role comparison
- ✅ Permission checking logic
- ✅ Decorator functionality
- ✅ Dependency functionality
- ✅ Request-scoped caching
- ✅ Audit logging
- ✅ Error handling

---

## Security Considerations

1. **JWT Validation**: All RBAC checks require valid JWT tokens
2. **Role Validation**: Roles are validated against enum values (case-insensitive)
3. **Permission Mapping**: Permissions are explicitly mapped to roles
4. **Audit Logging**: All access denials are logged with full context
5. **Error Messages**: Generic error messages prevent information leakage
6. **Request Caching**: Caching is scoped per request (not global)

---

## Migration Guide

### From Old Implementation

If you have existing code using the old RBAC implementation:

**Old:**
```python
from src.auth.rbac import RequiresRole
from src.auth.roles import Role

@router.get("/admin")
async def admin_endpoint(
    claims: JWTClaims = Depends(RequiresRole(Role.ADMIN))
):
    ...
```

**New (Decorator):**
```python
from src.auth.decorators import requires_role

@router.get("/admin")
@requires_role("Admin")
async def admin_endpoint(
    claims: JWTClaims = Depends(get_current_user_claims)
):
    ...
```

**New (Dependency - Still Works):**
```python
from src.auth.rbac import RequiresRole
from src.auth.roles import Role

@router.get("/admin")
async def admin_endpoint(
    claims: JWTClaims = Depends(RequiresRole(Role.ADMIN))
):
    ...
```

Both approaches are supported. Choose based on your preference.

---

**Status:** ✅ **IMPLEMENTATION COMPLETE**
