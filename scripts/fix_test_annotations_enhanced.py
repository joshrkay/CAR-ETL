#!/usr/bin/env python3
"""
Enhanced script to automatically fix missing type annotations in test files.

Handles:
- Test functions
- Pytest fixtures
- Class-based test methods
- Helper functions
"""

import re
import sys
from pathlib import Path
from typing import Generator


def add_fixture_types(content: str) -> tuple[str, int]:
    """Add type annotations to pytest fixtures based on their return statements."""

    # Pattern for fixtures without return type
    # Captures: @pytest.fixture\n def name(params):
    pattern = r'(@pytest\.fixture[^\n]*\n)(    )?def (\w+)\(([^)]*)\):'

    changes = 0

    def replace_func(match: re.Match[str]) -> str:
        nonlocal changes
        decorator = match.group(1)
        indent = match.group(2) or ''
        func_name = match.group(3)
        params = match.group(4)

        # Don't modify if already has return type
        if ' -> ' in content[match.start():match.end() + 50]:
            return match.group(0)

        # Try to infer return type from the function body
        # Find the function body (next ~50 lines)
        func_start = match.end()
        func_body = content[func_start:func_start + 2000]

        # Common patterns
        return_type = None

        if 'return Mock()' in func_body or 'return AsyncMock()' in func_body:
            from_mock = 'Mock'
            if 'AsyncMock' in func_body[:500]:
                from_mock = 'AsyncMock'
            return_type = from_mock
        elif 'return TestClient' in func_body:
            return_type = 'TestClient'
        elif 'return AuthContext' in func_body or 'Mock(spec=AuthContext)' in func_body:
            return_type = 'AuthContext'
        elif 'return supabase' in func_body.lower() or 'Client()' in func_body:
            return_type = 'Any'  # Supabase client
        elif 'Generator' in func_body or 'yield' in func_body:
            return_type = 'Generator'
        else:
            # Default to Any for complex fixtures
            return_type = 'Any'

        changes += 1
        return f'{decorator}{indent}def {func_name}({params}) -> {return_type}:'

    new_content = re.sub(pattern, replace_func, content)
    return new_content, changes


def add_test_function_types(content: str) -> tuple[str, int]:
    """Add -> None to test functions without return types."""

    # Pattern for test/async test functions without return type
    pattern = r'^(    )?(async )?def (test_\w+)\(([^)]*)\):'

    changes = 0

    def replace_func(match: re.Match[str]) -> str:
        nonlocal changes
        indent = match.group(1) or ''
        async_kw = match.group(2) or ''
        func_name = match.group(3)
        params = match.group(4)

        # Don't modify if already has return type
        if ' -> ' in content[match.start():match.end() + 50]:
            return match.group(0)

        changes += 1
        return f'{indent}{async_kw}def {func_name}({params}) -> None:'

    new_content = re.sub(pattern, replace_func, content, flags=re.MULTILINE)
    return new_content, changes


def add_imports_if_needed(content: str, needs_typing: bool = False) -> str:
    """Add necessary imports for type annotations."""

    lines = content.split('\n')
    import_section_end = 0

    # Find where imports end
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith('import ') and not line.startswith('from ') and not line.startswith('#') and not line.strip().startswith('"""') and not line.strip().startswith("'''"):
            import_section_end = i
            break

    new_imports = []

    if needs_typing and 'from typing import' not in content and 'import typing' not in content:
        # Check if we need Any, Generator, etc.
        if ' -> Any' in content or ' -> Generator' in content:
            new_imports.append('from typing import Any, Generator')

    if ' -> Mock' in content or ' -> AsyncMock' in content:
        if 'from unittest.mock import' in content:
            # Modify existing import
            for i, line in enumerate(lines):
                if 'from unittest.mock import' in line and 'Mock' not in line:
                    lines[i] = line.rstrip() + ', Mock, AsyncMock'
                    break
        else:
            new_imports.append('from unittest.mock import Mock, AsyncMock')

    if new_imports:
        lines.insert(import_section_end, '\n'.join(new_imports))

    return '\n'.join(lines)


def process_file(file_path: Path) -> tuple[bool, int]:
    """Process a single file to add type annotations."""

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        content = original_content
        total_changes = 0

        # Add fixture types
        content, fixture_changes = add_fixture_types(content)
        total_changes += fixture_changes

        # Add test function types
        content, test_changes = add_test_function_types(content)
        total_changes += test_changes

        # Add imports if needed
        if total_changes > 0:
            content = add_imports_if_needed(content, needs_typing=True)

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, total_changes

        return False, 0

    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False, 0


def main() -> None:
    """Main entry point."""

    if len(sys.argv) > 1:
        # Process specific file
        file_path = Path(sys.argv[1])
        if not file_path.exists():
            print(f"File not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        test_files = [file_path]
    else:
        # Process all test files
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
