# MyPy Error Completion Plan

## Current Status
- **Starting errors (this session)**: 592
- **Current errors**: 495
- **Progress**: 97 errors fixed (16.4% improvement)
- **Overall progress**: 537/1,032 errors fixed (52% complete)
- **src/ status**: ✅ 0 errors (100% clean)

## Remaining Work: 495 Errors

### Error Distribution
| Category | Count | % of Total |
|----------|-------|------------|
| no-untyped-def | 320 | 64.6% |
| untyped-decorator | 80+ | 16.2% |
| call-arg (Pydantic) | 40+ | 8.1% |
| operator | 14 | 2.8% |
| override | 12 | 2.4% |
| attr-defined | 7 | 1.4% |
| str-bytes-safe | 4 | 0.8% |
| arg-type | 4 | 0.8% |
| comparison-overlap | 3 | 0.6% |
| var-annotated | 3 | 0.6% |
| name-defined | 2 | 0.4% |
| list-item | 2 | 0.4% |
| Other | 4 | 0.8% |

---

## Phase 5: Test Fixture Parameters (320 errors) 🎯 HIGH PRIORITY

### Problem
Test methods in class-based tests have fixture parameters without type annotations:
```python
def test_search_basic(self, mock_supabase_client) -> None:  # ❌ mock_supabase_client lacks type
```

### Solution Strategy
**Option A: Enhance fix_nested_functions.py** (RECOMMENDED)
- Extend the existing script to handle test method fixture parameters
- Add pattern detection for common fixtures (client, mock, app, etc.)
- Infer types based on fixture name patterns

**Option B: Create new script fix_test_method_params.py**
- Dedicated script for test method parameters only
- Simpler logic focused on class-based tests
- Pattern matching for pytest fixtures

**Option C: Manual + mypy.ini exception**
- Add `disallow_untyped_defs = False` to tests section (already done)
- These errors shouldn't appear with current config
- May need to verify mypy.ini configuration

### Recommended Approach
1. Verify why `disallow_untyped_defs = False` isn't suppressing these
2. If needed, enhance `fix_nested_functions.py` to:
   - Detect class-based test methods (indent = 4 spaces, inside class)
   - Add `: Any` to fixture parameters
   - Run on all test files

### Expected Impact
- Errors reduced: 495 → 175 (65% reduction)
- Effort: Medium (2-3 hours if scripted)

---

## Phase 6: Hypothesis Decorator Configuration (80+ errors) 🎯 HIGH PRIORITY

### Problem
Property-based tests using `@given()` decorators from hypothesis library:
```python
@settings(deadline=5000, max_examples=50)
@given(st.text(min_size=1, max_size=1000))
def test_redact_no_email_leakage(self, text: str) -> None:  # ❌ Untyped decorator
```

### Root Cause
Hypothesis decorators are not typed, causing mypy to mark decorated functions as untyped.

### Solution
Add to `mypy.ini`:
```ini
[mypy-tests.*]
# Existing config...
disable_error_code = call-arg, untyped-decorator
```

**Alternative**: More targeted approach:
```ini
[mypy]
# Allow hypothesis decorators specifically
[mypy-tests.test_pii]
disable_error_code = untyped-decorator

[mypy-tests.test_redaction]
disable_error_code = untyped-decorator

[mypy-tests.test_pipeline_property_based]
disable_error_code = untyped-decorator
```

### Recommended Approach
1. Add `untyped-decorator` to global test disable list
2. Verify no false positives are hidden
3. Consider adding type stubs for hypothesis if available

### Expected Impact
- Errors reduced: 175 → 95 (46% reduction)
- Effort: Low (15 minutes)

---

## Phase 7: Pydantic call-arg Errors (40+ errors) 🎯 MEDIUM PRIORITY

### Problem
Pydantic models with optional fields require explicit None in tests:
```python
entity = EntityRecord(
    id=uuid4(),
    tenant_id=tenant_id,
    canonical_name="Acme",
    # ❌ Missing external_id, updated_at (optional fields)
)
```

### Root Cause
Mypy strict mode requires all Field() parameters to be passed, even if they have defaults.

### Current Config
Already have per-module overrides in `mypy.ini` for some models. Need to expand.

### Solution Strategy
**Option A: Expand mypy.ini overrides** (RECOMMENDED)
```ini
[mypy-tests.test_resolution]
disable_error_code = call-arg

[mypy-tests.test_extraction]
disable_error_code = call-arg

[mypy-tests.test_search]
disable_error_code = call-arg
```

**Option B: Fix test code**
- Add explicit None/default values in test instantiations
- More correct but tedious
- Makes tests more verbose

### Recommended Approach
1. Identify all test files with call-arg errors
2. Add per-file mypy.ini overrides
3. Document why (Pydantic optional fields in tests)

### Expected Impact
- Errors reduced: 95 → 55 (42% reduction)
- Effort: Low (30 minutes)

---

## Phase 8: Operator Type Inference (14 errors) 🎯 LOW PRIORITY

### Problem
Type inference fails for `in` operator and arithmetic:
```python
if key in config_dict:  # ❌ Unsupported right operand type for in ("object")
result = value + 1      # ❌ Unsupported operand types for + ("object" and "int")
```

### Root Cause
Mock objects or fixtures have `object` type instead of specific types.

### Solution Strategy
1. Add type annotations to fixture return types
2. Use `cast()` for mock objects
3. Add `# type: ignore[operator]` for unavoidable cases

### Files Affected
- test_bulk_upload.py (multiple occurrences)
- test_sharepoint_connector.py
- test_documents.py

### Recommended Approach
Review each case individually and:
1. Fix fixture return types where possible
2. Add explicit casts for mock objects
3. Use type ignore as last resort with explanatory comment

### Expected Impact
- Errors reduced: 55 → 41 (25% reduction)
- Effort: Medium (1-2 hours)

---

## Phase 9: Override Signature Mismatches (12 errors) 🎯 LOW PRIORITY

### Problem
Test mocks override async methods with incorrect signatures:
```python
class MockEmitter(IngestionEmitter):
    async def emit_file_reference(self, **kwargs: Any) -> Coroutine[Any, Any, None]:
        # ❌ Signature incompatible with supertype
```

### Root Cause
Base class expects specific parameters, mock uses **kwargs.

### Solution Strategy
**Option A: Match base class signature**
```python
async def emit_file_reference(
    self,
    file_id: str,
    tenant_id: UUID,
    metadata: dict[str, Any]
) -> None:  # Return None, not Coroutine
```

**Option B: Use type ignore**
```python
async def emit_file_reference(self, **kwargs: Any) -> None:  # type: ignore[override]
```

### Recommended Approach
1. Check base class signatures
2. Match signatures in test mocks
3. Use type ignore only if matching is impractical

### Expected Impact
- Errors reduced: 41 → 29 (29% reduction)
- Effort: Medium (1 hour)

---

## Phase 10: Miscellaneous Errors (29 errors) 🎯 LOW PRIORITY

### Categories

#### attr-defined (7 errors)
Mock attributes not recognized:
```python
mock.side_effect = Exception()  # ❌ Callable has no attribute "side_effect"
```
**Fix**: Use `# type: ignore[attr-defined]` for mock-specific attributes

#### str-bytes-safe (4 errors)
Byte string formatting:
```python
f"{byte_data}"  # ❌ Produces "b'abc'" not "abc"
```
**Fix**: Use `.decode()` or `{byte_data!r}`

#### comparison-overlap (3 errors)
Enum vs string comparisons:
```python
if event_type == "auth.login":  # ❌ EventType.AUTH_LOGIN != "auth.login"
```
**Fix**: Use enum values or .value property

#### var-annotated (3 errors)
Variables need type hints:
```python
saved_tokens = {}  # ❌ Need type annotation
```
**Fix**: `saved_tokens: dict[str, str] = {}`

#### name-defined (2 errors)
Missing imports:
```python
def foo() -> Any:  # ❌ Any not imported
```
**Fix**: Run `add_typing_imports.py`

#### list-item (2 errors)
List type mismatches:
```python
items = ["string", "another"]  # Expected list[dict[str, str]]
```
**Fix**: Correct the data structure

#### arg-type (4 errors)
Type incompatibilities:
```python
sanitize_error_message(None)  # ❌ Expected str
```
**Fix**: Add None checks or change function signature

#### Other (4 errors)
Review individually

### Expected Impact
- Errors reduced: 29 → 0 (100% reduction)
- Effort: Medium (2-3 hours)

---

## Execution Timeline

### Week 1: Core Automation (Phases 5-6)
**Day 1-2**: Phase 5 - Test fixture parameters
- Extend fix_nested_functions.py
- Test on sample files
- Run on all tests
- Commit: "feat(types): Add types to test method fixture parameters"

**Day 2**: Phase 6 - Hypothesis decorators
- Update mypy.ini
- Verify error reduction
- Commit: "fix(types): Configure mypy to handle hypothesis decorators"

**Expected**: 495 → 95 errors (80% reduction)

### Week 2: Configuration & Targeted Fixes (Phases 7-9)
**Day 3**: Phase 7 - Pydantic call-arg
- Add mypy.ini overrides
- Test changes
- Commit: "fix(types): Add call-arg exceptions for Pydantic test fixtures"

**Day 4**: Phase 8 - Operator errors
- Review each case
- Fix fixture types
- Add casts/ignores
- Commit: "fix(types): Resolve operator type inference errors"

**Day 5**: Phase 9 - Override errors
- Fix test mock signatures
- Commit: "fix(types): Fix override signature mismatches in test mocks"

**Expected**: 95 → 29 errors (69% reduction)

### Week 3: Final Cleanup (Phase 10)
**Day 6-7**: Miscellaneous fixes
- Fix each category systematically
- Test thoroughly
- Commit: "fix(types): Resolve remaining miscellaneous type errors"

**Expected**: 29 → 0 errors (100% reduction)

---

## Success Criteria

### Phase Completion
- ✅ All automated scripts run without errors
- ✅ No syntax errors introduced
- ✅ Tests still pass
- ✅ CI mypy check passes

### Final Completion
- ✅ `mypy src/` returns 0 errors
- ✅ `mypy tests/` returns 0 errors (or acceptable baseline)
- ✅ All scripts documented and committed
- ✅ MYPY_IMPROVEMENT_ROADMAP.md updated with completion status

---

## Risk Mitigation

### Risks
1. **Automation introduces syntax errors**
   - Mitigation: Always validate with ast.parse()
   - Run mypy after each batch
   - Commit frequently

2. **Type ignores hide real issues**
   - Mitigation: Document each ignore with explanation
   - Prefer fixes over ignores
   - Review all ignores in PR

3. **Tests break after changes**
   - Mitigation: Run test suite after each phase
   - Keep changes minimal and focused
   - Revert quickly if tests fail

4. **CI failures**
   - Mitigation: Test mypy locally with same config as CI
   - Verify requirements-typecheck.txt is complete
   - Push to branch frequently

---

## Alternative Approach: Aggressive Configuration

If automation is too time-consuming, consider:

### Option: Disable strict mode for tests
```ini
[mypy-tests.*]
disallow_untyped_defs = False
disallow_untyped_decorators = False
disable_error_code = call-arg, untyped-decorator, operator, override
```

**Pros**:
- Immediate error reduction to ~0
- Focus on keeping src/ clean
- Less maintenance burden

**Cons**:
- Tests lose type safety benefits
- Potential issues missed in test code
- Less learning value

**Recommendation**: Use aggressive config as fallback if Phase 5 proves too difficult.

---

## Current Session Summary

### Completed
- ✅ Created fix_nested_functions.py automation
- ✅ Fixed 93 nested functions across 24 files
- ✅ Fixed 25 missing Any imports
- ✅ Reduced errors from 592 → 495

### Next Steps
1. Start Phase 5: Test fixture parameter automation
2. Verify mypy.ini configuration for tests
3. Decide on automation vs configuration approach

### Key Decision Point
**Before Phase 5**: Determine if we want:
- **Path A**: Full type safety in tests (automation, more work)
- **Path B**: Pragmatic approach (configuration, less work)
- **Path C**: Hybrid (automate easy cases, configure rest)

**Recommendation**: Path C - Automate common patterns, use configuration for edge cases.
