#!/usr/bin/env python3
"""
Automatically fix missing type annotations in test files.

This script adds type annotations to test functions that are missing them.
Handles both test functions and pytest fixtures.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


def fix_test_function_annotations(content: str) -> str:
    """Add return type annotations to test functions missing them."""

    # Pattern for test functions without return type annotation
    # Matches: def test_something(...): or    def test_something(...):
    # but not: def test_something(...) -> ...:
    # Handles both top-level and indented functions (class methods)
    pattern = r'^(\s*)((?:@[\w.]+(?:\([^)]*\))?\s*\n\s*)*)((?:async\s+)?def (test_\w+|setup\w*|teardown\w*)\([^)]*\))(\s*:)'

    def replace_func(match: re.Match[str]) -> str:
        indent = match.group(1) or ''
        decorators = match.group(2) or ''
        func_def = match.group(3)
        func_name = match.group(4)
        colon = match.group(5)

        # Don't add annotation if it's a fixture
        if '@pytest.fixture' in decorators:
            return match.group(0)

        # Don't add annotation if it's a contextmanager
        if '@contextmanager' in decorators:
            return match.group(0)

        # Check if already has annotation
        if ' -> ' in func_def:
            return match.group(0)

        return f'{indent}{decorators}{func_def} -> None{colon}'

    return re.sub(pattern, replace_func, content, flags=re.MULTILINE)


def fix_fixture_annotations(content: str) -> str:
    """Add return type annotations to pytest fixtures missing them."""

    # Pattern for fixtures without return type annotation
    # Matches: @pytest.fixture\ndef something(...):
    pattern = r'(@pytest\.fixture[^\n]*\n)(def \w+\([^)]*\))(\s*:)'

    def replace_func(match: re.Match[str]) -> str:
        decorator = match.group(1)
        func_def = match.group(2)
        colon = match.group(3)

        # For now, we'll skip fixtures since they need specific return types
        # This would require analyzing the function body
        return match.group(0)

    return content  # Skip for now - fixtures need careful analysis


def count_annotations_added(original: str, fixed: str) -> int:
    """Count how many annotations were added."""
    original_count = len(re.findall(r'def \w+.*\) -> \w+:', original))
    fixed_count = len(re.findall(r'def \w+.*\) -> \w+:', fixed))
    return fixed_count - original_count


def process_file(file_path: Path) -> Tuple[bool, int]:
    """
    Process a single file to add type annotations.

    Returns:
        Tuple of (was_modified, num_changes)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        # Apply all fixes
        fixed_content = original_content
        fixed_content = fix_test_function_annotations(fixed_content)
        fixed_content = fix_fixture_annotations(fixed_content)

        if fixed_content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)

            num_changes = count_annotations_added(original_content, fixed_content)
            return True, num_changes

        return False, 0

    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False, 0


def main() -> None:
    """Main entry point."""
    tests_dir = Path("tests")

    if not tests_dir.exists():
        print("tests/ directory not found", file=sys.stderr)
        sys.exit(1)

    test_files = list(tests_dir.glob("test_*.py"))

    if not test_files:
        print("No test files found", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(test_files)} test files...")

    total_modified = 0
    total_changes = 0

    for file_path in sorted(test_files):
        was_modified, num_changes = process_file(file_path)
        if was_modified:
            total_modified += 1
            total_changes += num_changes
            print(f"  ✓ {file_path.name}: {num_changes} functions annotated")

    print(f"\nSummary:")
    print(f"  Files modified: {total_modified}/{len(test_files)}")
    print(f"  Total functions annotated: {total_changes}")


if __name__ == "__main__":
    main()
