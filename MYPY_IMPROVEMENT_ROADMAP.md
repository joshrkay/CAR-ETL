# Mypy Error Reduction Roadmap

## Current State
- **Total errors:** 1,012
- **src/ errors:** 0 ✅ (100% clean)
- **tests/ errors:** ~1,012

## Error Distribution

| Error Type | Count | % of Total | Location |
|------------|-------|------------|----------|
| `no-untyped-def` | 883 | 87% | tests/ |
| `call-arg` | 45 | 4% | tests/ (Pydantic models) |
| `untyped-decorator` | 19 | 2% | tests/ (pytest fixtures) |
| `operator` | 14 | 1% | tests/ |
| `return-value` | 13 | 1% | tests/ |
| Other | 38 | 4% | tests/ |

## Top 10 Files by Error Count

1. `tests/test_rbac.py` - 56 errors
2. `tests/test_google_drive_connector.py` - 52 errors
3. `tests/test_extraction.py` - 50 errors
4. `tests/test_extraction_worker.py` - 49 errors
5. `tests/test_error_sanitizer.py` - 47 errors
6. `tests/test_audit.py` - 43 errors
7. `tests/test_search.py` - 41 errors
8. `tests/test_document_upload.py` - 38 errors
9. `tests/test_file_validator.py` - 37 errors
10. `tests/test_auth.py` - 36 errors

## Reduction Strategy

### Phase 1: Low-Hanging Fruit (Target: -300 errors, ~1 hour)

**Approach:** Batch-fix simple test function annotations

1. **Use automation script** (`scripts/fix_test_annotations.py`)
   - Already fixed 55 functions
   - Can expand pattern matching to handle more cases

2. **Target files with most `no-untyped-def` errors**
   ```bash
   # Process top 10 test files
   for file in test_rbac test_google_drive_connector test_extraction; do
     python scripts/fix_test_annotations.py tests/test_${file}.py
   done
   ```

3. **Expected reduction:** 300-400 `no-untyped-def` errors
   - Simple `def test_*():` → `def test_*() -> None:`
   - Automated, safe, no logic changes

### Phase 2: Pydantic Model Fixes (Target: -45 errors, ~30 min)

**Problem:** Missing required arguments in Pydantic model constructors

**Example from tests:**
```python
# Error: Missing named argument "section_header" for "ChunkMatch"
chunk = ChunkMatch(text="...", score=0.9)
# Fix:
chunk = ChunkMatch(text="...", score=0.9, section_header=None)
```

**Approach:**
1. Review model definitions to find required fields
2. Update test instantiations to include all required fields
3. Or add default values to model definitions if appropriate

**Expected reduction:** 45 `call-arg` errors

### Phase 3: Pytest Fixture Types (Target: -19 errors, ~20 min)

**Problem:** Untyped pytest fixtures

**Example:**
```python
@pytest.fixture
def mock_client():  # Error: untyped-decorator
    return MockClient()

# Fix:
@pytest.fixture
def mock_client() -> MockClient:
    return MockClient()
```

**Approach:**
1. Add return type annotations to all pytest fixtures
2. Use proper types for fixture returns

**Expected reduction:** 19 `untyped-decorator` errors

### Phase 4: Type Narrowing & Operators (Target: -27 errors, ~45 min)

**Problem:** Type checking issues in test assertions

**Examples:**
```python
# operator error: Unsupported operand types for + ("object" and "int")
assert response.count + 1 == 10
# Fix: Add type hint or cast
assert cast(int, response.count) + 1 == 10

# return-value error: incompatible return type
def helper():
    return some_any_value  # type: Any
# Fix: Add proper return type or cast
def helper() -> SpecificType:
    return cast(SpecificType, some_any_value)
```

**Expected reduction:** 27 errors (14 operator + 13 return-value)

### Phase 5: Miscellaneous (Target: -38 errors, ~1 hour)

Handle remaining error types:
- `override` (12) - Add proper `@override` decorator or fix signatures
- `attr-defined` (8) - Fix attribute access or add proper types
- `arg-type` (8) - Fix function argument types
- Other small issues

## Implementation Plan

### Quick Win Approach (1-2 hours total)
Focus on **Phase 1** only:
- Run enhanced automation script
- Get 300+ errors down to ~700
- Keep test code maintainable

### Comprehensive Approach (4-5 hours total)
Execute all 5 phases:
- Reduce from 1,012 → ~621 errors (Phases 1-5)
- Potentially get below 500 with thorough cleanup

### Aggressive Approach (8-10 hours)
- Execute all phases
- Add comprehensive type hints to test helpers
- Add types to complex test fixtures
- Target: <200 total errors

## Recommended Next Steps

I recommend **Phase 1 + Phase 2** as the next PR:

### Why?
1. **High Impact:** Fixes ~345 errors (34% reduction)
2. **Low Risk:** Automated + straightforward model fixes
3. **Fast:** Can be completed in 1.5 hours
4. **Maintainable:** Doesn't over-complicate test code

### How?
```bash
# 1. Enhance automation script to handle more patterns
# 2. Run on top 15 test files
python scripts/fix_test_annotations.py --batch tests/

# 3. Fix Pydantic call-arg errors
# Manual review of 45 model instantiations

# 4. Run regression check
python scripts/mypy_regression_check.py check

# 5. Commit & push
git commit -m "feat(types): reduce test type errors by 345 (Phase 1+2)"
```

### Expected Outcome
- **Before:** 1,012 errors
- **After:** ~667 errors
- **Reduction:** 345 errors (34%)
- **Time:** 1.5 hours

## Long-term Strategy

### Maintenance
1. **Pre-commit hook:** Run mypy regression check before each commit
2. **New test guideline:** All new test functions must have type annotations
3. **Gradual improvement:** Fix errors in files you're already modifying

### Future Phases
- Phase 3-5 can be done incrementally
- No rush - test typing is optional but beneficial
- Focus on high-value areas (integration tests, complex fixtures)

## Metrics to Track

| Metric | Current | Phase 1+2 | Phase 3-5 | Target |
|--------|---------|-----------|-----------|--------|
| Total errors | 1,012 | ~667 | ~400 | <200 |
| src/ errors | 0 | 0 | 0 | 0 |
| tests/ errors | 1,012 | ~667 | ~400 | <200 |
| % reduction | - | 34% | 60% | 80% |

## Conclusion

**Recommended action:** Execute Phase 1 + Phase 2 in a follow-up PR
- Fast, safe, high-impact
- Gets us to ~667 errors (34% reduction)
- Maintains code quality without over-engineering tests

**Do you want me to proceed with Phase 1 + Phase 2?**
