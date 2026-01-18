# Remaining MyPy Errors Analysis (194 Total)

**Current Status:** 838/1,032 errors fixed (81% complete)
- src/: 0 errors ✅
- tests/: 194 errors

---

## Error Categories (Prioritized by Impact)

### 🎯 Category 1: Missing Any Imports (18 errors) - CRITICAL & EASY
**Impact:** Blocks mypy from checking rest of file
**Effort:** 2 minutes
**Fix:** Run `add_typing_imports.py`

**Files affected:**
```bash
python -m mypy tests/ 2>&1 | grep 'Name "Any" is not defined' | cut -d: -f1 | sort -u
```

**Action:**
```bash
python scripts/add_typing_imports.py $(python -m mypy tests/ 2>&1 | grep 'Name "Any" is not defined' | cut -d: -f1 | sort -u | tr '\n' ' ')
```

---

### 🎯 Category 2: Hypothesis Decorators (80+ errors) - HIGH PRIORITY, EASY
**Impact:** 80 errors from property-based tests
**Effort:** 5 minutes
**Fix:** Add to mypy.ini

**Root Cause:** `@given()` and `@settings()` decorators from hypothesis library are untyped

**Affected Functions:**
- test_redact_* (PII tests)
- test_presidio_* (Presidio tests)
- test_process_document_* (document processing)
- test_log_* (audit logging)
- test_multi_tenant_* (tenant isolation)
- Route handlers: delete_document, admin_endpoint, etc.

**Solution:**
```ini
# In mypy.ini under [mypy-tests.*] section
disable_error_code = call-arg, untyped-decorator
```

**Expected:** 194 → ~110 errors

---

### 🎯 Category 3: Pydantic call-arg (41 errors) - MEDIUM PRIORITY, EASY
**Impact:** Pydantic models with optional fields
**Effort:** 10 minutes
**Fix:** Expand mypy.ini per-file overrides

**Breakdown:**
- ChunkMatch.section_header: 7 errors
- FieldDefinition (values, aliases): 8 errors
- SearchRequest (filters, enable_reranking): 8 errors
- EntityRecord (external_id, updated_at): 6 errors
- AuditEvent (user_agent, resource_type, resource_id, ip_address): 5 errors
- AskRequest.document_ids: 3 errors
- ExtractedField.quote: 2 errors
- AuthContext.tenant_slug: 2 errors

**Root Cause:** These fields have `Field(default=...)` or `Field(None)` but mypy strict mode still requires them

**Files Affected:**
```
tests/test_search.py (ChunkMatch, SearchRequest)
tests/test_extraction.py (FieldDefinition)
tests/test_resolution.py (EntityRecord)
tests/test_audit.py (AuditEvent)
tests/test_rag_integration.py (AskRequest)
tests/test_rbac.py (AuthContext)
```

**Solution:**
```ini
# Add to mypy.ini
[mypy-tests.test_search]
disable_error_code = call-arg

[mypy-tests.test_extraction]
disable_error_code = call-arg

[mypy-tests.test_resolution]
disable_error_code = call-arg

[mypy-tests.test_audit]
disable_error_code = call-arg

[mypy-tests.test_rag_integration]
disable_error_code = call-arg
```

**Expected:** ~110 → ~69 errors

---

### 🎯 Category 4: Operator Type Inference (14 errors) - MEDIUM PRIORITY, MODERATE
**Impact:** Type system can't infer mock object types
**Effort:** 30-60 minutes
**Fix:** Add type annotations or casts

**Breakdown:**
- 11× "Unsupported right operand type for in ("object")"
- 2× "Unsupported operand types for + ("object" and "int")"
- 1× "Unsupported right operand type for in ("set[str] | None")"

**Examples:**
```python
# Problem:
if key in config_dict:  # config_dict is inferred as 'object'

# Solution 1: Type hint the fixture
@pytest.fixture
def config_dict() -> dict[str, Any]:
    return {"key": "value"}

# Solution 2: Add cast
from typing import cast
if key in cast(dict, config_dict):

# Solution 3: Type ignore (last resort)
if key in config_dict:  # type: ignore[operator]
```

**Files to Review:**
```bash
python -m mypy tests/ 2>&1 | grep "\[operator\]" | cut -d: -f1 | sort -u
```

**Expected:** ~69 → ~55 errors

---

### 🎯 Category 5: Override Signature Mismatches (12 errors) - LOW PRIORITY, MODERATE
**Impact:** Test mocks don't match base class signatures
**Effort:** 30 minutes
**Fix:** Update mock signatures

**Breakdown:**
- emit_file_reference: 6 errors
- emit_deletion_reference: 6 errors

**Problem:**
```python
# Base class (src/connectors/google_drive/interfaces.py)
class IngestionEmitter:
    async def emit_file_reference(
        self,
        file_id: str,
        tenant_id: UUID,
        metadata: dict[str, Any]
    ) -> None:
        ...

# Test mock (tests/test_google_drive_connector.py)
class MockEmitter(IngestionEmitter):
    async def emit_file_reference(self, **kwargs: Any) -> Coroutine[Any, Any, None]:
        # ❌ Signature mismatch: **kwargs vs specific params
        # ❌ Return type: Coroutine vs None
        ...
```

**Solution:**
```python
# Option 1: Match the signature exactly
class MockEmitter(IngestionEmitter):
    async def emit_file_reference(
        self,
        file_id: str,
        tenant_id: UUID,
        metadata: dict[str, Any]
    ) -> None:  # Match return type
        ...

# Option 2: Type ignore if **kwargs is needed
class MockEmitter(IngestionEmitter):
    async def emit_file_reference(self, **kwargs: Any) -> None:  # type: ignore[override]
        ...
```

**File:** `tests/test_google_drive_connector.py`

**Expected:** ~55 → ~43 errors

---

### 🎯 Category 6: Attribute Errors (7 errors) - LOW PRIORITY, EASY
**Impact:** Mock object attributes not recognized
**Effort:** 10 minutes
**Fix:** Add type ignores

**Breakdown:**
- EmailIngestionService._calculate_hash: 3 errors
- Callable attributes (side_effect, call_count, __name__): 4 errors

**Examples:**
```python
# Problem:
mock_func.side_effect = Exception()  # ❌ Callable has no attribute "side_effect"

# Solution:
mock_func.side_effect = Exception()  # type: ignore[attr-defined]

# Or specify mock type:
from unittest.mock import Mock
mock_func: Mock = Mock()
mock_func.side_effect = Exception()  # ✅ OK
```

**Expected:** ~43 → ~36 errors

---

### 🎯 Category 7: Comparison Overlaps (3 errors) - LOW PRIORITY, EASY
**Impact:** Enum vs string comparisons
**Effort:** 5 minutes
**Fix:** Use .value property

**Examples:**
```python
# Problem:
if event_type == "auth.login":  # event_type is EventType enum

# Solution 1: Use .value
if event_type.value == "auth.login":

# Solution 2: Compare enum to enum
if event_type == EventType.AUTH_LOGIN:

# Solution 3: Type ignore
if event_type == "auth.login":  # type: ignore[comparison-overlap]
```

**Expected:** ~36 → ~33 errors

---

### 🎯 Category 8: Variable Annotations (3 errors) - LOW PRIORITY, TRIVIAL
**Impact:** Variables need explicit types
**Effort:** 2 minutes
**Fix:** Add type hints

**Examples:**
```python
# Before:
saved_tokens = {}  # ❌ Need type annotation
mock_tables = {}   # ❌ Need type annotation
chunks = []        # ❌ Need type annotation

# After:
saved_tokens: dict[str, str] = {}
mock_tables: dict[str, Any] = {}
chunks: list[Any] = []
```

**Expected:** ~33 → ~30 errors

---

### 🎯 Category 9: str-bytes-safe (4 errors) - LOW PRIORITY, EASY
**Impact:** Byte string formatting warnings
**Effort:** 5 minutes
**Fix:** Use .decode() or !r formatter

**Examples:**
```python
# Problem:
f"{byte_data}"  # Produces "b'abc'" not "abc"

# Solution 1: Decode
f"{byte_data.decode()}"

# Solution 2: Use repr formatter if b'abc' is intended
f"{byte_data!r}"

# Solution 3: Type ignore
f"{byte_data}"  # type: ignore[str-bytes-safe]
```

**Expected:** ~30 → ~26 errors

---

### 🎯 Category 10: arg-type (6 errors) - LOW PRIORITY, MODERATE
**Impact:** Type incompatibilities
**Effort:** 20 minutes
**Fix:** Add None checks or change types

**Examples:**
```python
# Problem 1: None passed where str expected
sanitize_error_message(None)  # ❌

# Solution:
if error_msg is not None:
    sanitize_error_message(error_msg)

# Problem 2: add_middleware type mismatch
app.add_middleware(AuthMiddleware)  # ❌

# Solution: Check Starlette docs for proper usage
app.add_middleware(AuthMiddleware, config=auth_config)
```

**Expected:** ~26 → ~20 errors

---

### 🎯 Category 11: no-untyped-def (3 errors) - LOW PRIORITY, INVESTIGATE
**Impact:** Remaining functions without types
**Effort:** 10 minutes
**Fix:** Manual inspection

**Action:**
```bash
python -m mypy tests/ 2>&1 | grep "no-untyped-def"
```

These might be edge cases our script missed.

**Expected:** ~20 → ~17 errors

---

### 🎯 Category 12: list-item (2 errors) - LOW PRIORITY, TRIVIAL
**Impact:** Wrong types in lists
**Effort:** 2 minutes
**Fix:** Correct the data structure

**Example:**
```python
# Problem:
items = ["string", "another"]  # Expected list[dict[str, str]]

# Solution:
items = [{"key": "string"}, {"key": "another"}]
```

**Expected:** ~17 → ~15 errors

---

## Execution Strategy

### 🚀 Quick Wins (20 minutes → ~110 errors)
1. ✅ **Category 1:** Run add_typing_imports.py → 176 errors
2. ✅ **Category 2:** Add untyped-decorator to mypy.ini → ~96 errors
3. ✅ **Category 3:** Add call-arg overrides → ~55 errors

### 🎯 Medium Effort (1-2 hours → ~20 errors)
4. **Category 4:** Fix operator errors → ~41 errors
5. **Category 5:** Fix override signatures → ~29 errors
6. **Category 6:** Add attr-defined ignores → ~22 errors

### 🧹 Final Cleanup (30 minutes → 0 errors)
7. **Categories 7-12:** Fix remaining misc errors → 0 errors ✅

---

## Recommended Next Steps

### Option A: Sprint to Finish (3 hours total)
Execute all categories sequentially, finish everything today.

### Option B: Quick Wins Only (20 minutes)
Do categories 1-3, reduce errors by 72% with minimal effort.
- 194 → ~55 errors
- Can finish rest later

### Option C: Complete Configuration (30 minutes)
Categories 1-3 + 6-12 (all config/ignore fixes)
- 194 → ~29 errors
- Only leaves operator and override errors (manual code fixes)

---

## Files That Need the Most Attention

Based on error frequency:

1. **tests/test_audit.py** - 15+ errors (Hypothesis decorators, Pydantic)
2. **tests/test_google_drive_connector.py** - 12 errors (override signatures)
3. **tests/test_pii.py** - 10+ errors (Hypothesis decorators)
4. **tests/test_search.py** - 8 errors (Pydantic call-arg)
5. **tests/test_extraction.py** - 8 errors (Pydantic call-arg)

---

## Success Metrics

| Milestone | Errors | % Complete | Effort |
|-----------|--------|------------|--------|
| **Current** | 194 | 81% | - |
| After Quick Wins | ~55 | 95% | 20 min |
| After Medium Effort | ~20 | 98% | 2 hrs |
| After Cleanup | 0 | 100% ✅ | 30 min |

---

## Key Decision

**What's your priority?**

- **Speed:** Option B (20 min, 72% reduction)
- **Balance:** Option C (30 min, 85% reduction)
- **Completion:** Option A (3 hrs, 100% clean)

All three options move us significantly forward!
