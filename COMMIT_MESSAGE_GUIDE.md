# Git Commit Message Guide (Following .cursorrules)

## Commit Message Format

According to `.cursorrules`, commit messages should follow this format:

```
feat(scope): description

Body: Explain the "WHY", not just the "WHAT". Reference the User Story/Ticket ID.
```

---

## Examples for CAR Platform

### Feature Commits

```
feat(tenants): add tenant provisioning API

Implements POST /api/v1/tenants endpoint to create isolated databases per tenant.
Ensures data isolation at the database level. Fixes US-2.1.
```

```
feat(auth): implement JWT claims middleware

Adds tenant_id and roles claims to JWT tokens via Auth0 Actions.
Enables request-level authorization context. Fixes US-3.2.
```

```
feat(middleware): add tenant context resolution

Implements middleware to route requests to correct tenant database.
Enforces data isolation at application layer. Fixes US-4.1.
```

### Fix Commits

```
fix(encryption): remove hardcoded salt in PBKDF2

Removes security vulnerability where hardcoded salt enabled rainbow table attacks.
Requires base64-encoded keys only. Fixes SEC-1.
```

```
fix(tenant-resolver): add UUID validation

Adds explicit UUID format validation for tenant_id.
Prevents invalid tenant IDs from reaching database. Fixes US-4.2.
```

### Refactor Commits

```
refactor(provisioning): reduce function complexity

Extracts helper methods from provision_tenant to meet complexity limit.
Reduces from 15 to 7 complexity. Fixes CODE-1.
```

---

## Commit Message Structure

### Title (Required)
- Format: `type(scope): description`
- Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
- Scope: Component name (e.g., `tenants`, `auth`, `middleware`)
- Description: Concise, imperative mood

### Body (Recommended for significant changes)
- Explain the "WHY"
- Reference User Story/Ticket ID
- Describe impact/benefit

### Breaking Changes (If applicable)
- Use `BREAKING CHANGE:` prefix
- Describe what breaks and migration path

---

## Good vs Bad Examples

### ✅ Good

```
feat(tenants): add database provisioning with rollback

Implements atomic tenant provisioning with automatic rollback on failure.
Ensures no orphaned databases. Fixes US-2.1.
```

### ❌ Bad

```
Update code
```

### ✅ Good

```
fix(encryption): remove PBKDF2 fallback with hardcoded salt

Eliminates security vulnerability where all derived keys were identical.
Requires base64-encoded keys only. Fixes SEC-1.
```

### ❌ Bad

```
Fixed encryption bug
```

---

## For Your Initial Commit

Use this commit message:

```
feat: initial commit - CAR Platform implementation

Implements core CAR Platform features:
- Tenant provisioning with isolated databases
- JWT claims (tenant_id, roles) via Auth0 Actions
- Tenant context middleware for request routing
- Encryption service for connection strings
- Control plane database schema
- Comprehensive test coverage

All code follows .cursorrules standards.
```

---

**Status:** ✅ **COMMIT MESSAGE GUIDE READY**

Use these formats when committing code.
