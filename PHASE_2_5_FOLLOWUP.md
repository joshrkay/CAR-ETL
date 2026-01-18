# GitHub Issue: Mypy Phase 2-5 Improvements

**Title:** Continue mypy error reduction (Phase 2-5)

**Labels:** `enhancement`, `technical-debt`, `type-safety`

---

## Summary

Continue the mypy type improvement work from PR #XX (Phase 1). We've reduced errors from 1,223 to 660 (46% reduction), with src/ at 100% coverage. This issue tracks the remaining 660 test errors across 4 additional phases.

## Current State (After Phase 1)

✅ **Completed:**
- src/ errors: 0 (100% type-safe)
- Total errors reduced: 563 (46% reduction)
- Test annotations added: 654 functions
- Automation tools: Built and working

📊 **Remaining (660 errors in tests/):**
- 521 `no-untyped-def` (complex test functions)
- 45 `call-arg` (Pydantic optional fields)
- 23 `return-value` (type narrowing needed)
- 19 `untyped-decorator` (pytest fixtures)
- 52 other minor issues

## Proposed Phases

### Phase 2: Fix Pydantic call-arg Errors (~30 min)
**Target:** -45 errors

**Approach:**
1. Review Pydantic model definitions in `src/rag/models.py`, `src/extraction/`, etc.
2. Update test instantiations to include all required fields
3. Alternative: Add default values to model definitions where appropriate

**Example Fix:**
```python
# Before
chunk = ChunkMatch(id=uuid, document_id=uuid, content="...", similarity=0.9)

# After
chunk = ChunkMatch(
    id=uuid,
    document_id=uuid,
    content="...",
    similarity=0.9,
    section_header=None  # Add missing optional field
)
```

**Files to modify:** ~10-15 test files

---

### Phase 3: Add Fixture Type Annotations (~20 min)
**Target:** -19 errors

**Approach:**
1. Add return type annotations to pytest fixtures
2. Use proper types based on what the fixture returns

**Example Fix:**
```python
# Before
@pytest.fixture
def mock_client():
    return MockClient()

# After
@pytest.fixture
def mock_client() -> MockClient:
    return MockClient()
```

**Files to modify:** ~8-10 test files

---

### Phase 4: Type Narrowing & Operators (~45 min)
**Target:** -37 errors (23 return-value + 14 operator)

**Approach:**
1. Add type hints or casts for operator issues
2. Fix return type mismatches

**Example Fixes:**
```python
# Operator error fix
assert cast(int, response.count) + 1 == 10

# Return value fix
def helper() -> SpecificType:
    return cast(SpecificType, some_value)
```

**Files to modify:** ~15-20 test files

---

### Phase 5: Complex Test Functions (~2-3 hours)
**Target:** -521 errors

**Approach:**
1. Add type annotations to test function parameters
2. Focus on high-value test files first
3. Use automation where possible

**Example Fix:**
```python
# Before
def test_with_params(param1, param2):
    ...

# After
def test_with_params(param1: str, param2: int) -> None:
    ...
```

**Strategy:**
- Start with integration tests (high value)
- Use gradual typing (annotate as you touch files)
- Optionally skip low-value tests

---

## Estimated Effort

| Phase | Time | Reduction | Difficulty |
|-------|------|-----------|------------|
| 2 | 30m | -45 | Easy |
| 3 | 20m | -19 | Easy |
| 4 | 45m | -37 | Medium |
| 5 | 2-3h | -521 | Medium |
| **Total** | **4-5h** | **-622** | **Mixed** |

## Success Criteria

- [ ] Phases 2-4 completed (reduce to ~559 errors)
- [ ] Phase 5: At least 50% of remaining errors fixed (reduce to ~280)
- [ ] src/ maintains 0 errors
- [ ] Regression test suite still passing
- [ ] No functional changes

## Alternative Approach: Incremental

Instead of dedicated effort, we can fix these incrementally:
- Add rule: "If you modify a test file, add type annotations"
- Fix 10-20 errors per PR when touching tests
- Reach goal in 3-6 months naturally

## Resources

- **Roadmap:** `MYPY_IMPROVEMENT_ROADMAP.md`
- **Regression script:** `scripts/mypy_regression_check.py`
- **Automation tool:** `scripts/fix_test_annotations.py`
- **Docs:** `MYPY_REGRESSION_TESTING.md`

## Non-Goals

- ❌ Perfect type coverage (tests don't need 100%)
- ❌ Over-engineering test code
- ❌ Blocking new features for type cleanup

## Decision

**Recommendation:** Execute Phases 2-4 in next PR (1.5 hours), handle Phase 5 incrementally.

This gets us to ~559 errors (54% reduction from baseline) with minimal effort, while keeping test code maintainable.
