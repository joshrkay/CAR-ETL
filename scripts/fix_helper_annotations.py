#!/usr/bin/env python3
"""
Fix missing type annotations in test helper functions.

Handles:
- Helper functions (non-test functions)
- Nested functions inside tests
- Functions with parameters
- Functions with return values
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


def has_return_statement(func_body: str) -> bool:
    """Check if function has any return statements with values."""
    # Match return statements that aren't just "return" or "return None"
    return bool(re.search(r'return\s+(?!None\s*$)(?!$).+', func_body))


def infer_param_type(param_name: str, func_body: str) -> str:
    """Infer parameter type from usage patterns."""
    # Escape special regex characters in param name
    safe_param = re.escape(param_name)

    try:
        # Common patterns for inferring types
        if re.search(rf'\b{safe_param}\s*==\s*["\']', func_body):
            return "str"
        elif re.search(rf'\b{safe_param}\s*==\s*\d+', func_body):
            return "int"
        elif re.search(rf'\b{safe_param}\s*==\s*(True|False)', func_body):
            return "bool"
        elif re.search(rf'\[{safe_param}\]', func_body):
            return "str"  # Likely a key
    except re.error:
        pass  # If regex fails, fall through to heuristics

    # Name-based heuristics
    if "client" in param_name.lower():
        return "Any"
    elif "mock" in param_name.lower():
        return "Any"
    else:
        return "Any"


def fix_helper_function_annotations(content: str) -> Tuple[str, int]:
    """Add type annotations to helper functions missing them."""

    lines = content.split('\n')
    changes = 0
    i = 0

    while i < len(lines):
        line = lines[i]

        # Match function definitions without type annotations
        # Pattern: def function_name(params):
        match = re.match(r'^(\s*)def\s+(\w+)\((.*?)\)(\s*):(.*)$', line)

        if match:
            indent = match.group(1)
            func_name = match.group(2)
            params = match.group(3)
            space_before_colon = match.group(4)
            rest = match.group(5)

            # Skip if already has return type annotation
            if '->' in line:
                i += 1
                continue

            # Skip test_ functions (already handled by previous script)
            if func_name.startswith('test_'):
                i += 1
                continue

            # Collect function body to analyze
            func_body_lines = []
            j = i + 1
            if j < len(lines):
                # Get indentation of first line in function
                func_indent_match = re.match(r'^(\s+)', lines[j])
                if func_indent_match:
                    func_indent = func_indent_match.group(1)
                    while j < len(lines):
                        if lines[j].strip() and not lines[j].startswith(func_indent):
                            break
                        func_body_lines.append(lines[j])
                        j += 1

            func_body = '\n'.join(func_body_lines)

            # Process parameters
            if params.strip():
                # Split parameters
                param_list = [p.strip() for p in params.split(',')]
                typed_params = []

                for param in param_list:
                    # Skip if already typed
                    if ':' in param:
                        typed_params.append(param)
                    # Skip self
                    elif param == 'self':
                        typed_params.append(param)
                    # Add type annotation
                    else:
                        # Extract parameter name (handle defaults)
                        param_name = param.split('=')[0].strip()
                        param_type = infer_param_type(param_name, func_body)

                        # Preserve default value if exists
                        if '=' in param:
                            default_val = param.split('=', 1)[1].strip()
                            typed_params.append(f'{param_name}: {param_type} = {default_val}')
                        else:
                            typed_params.append(f'{param_name}: {param_type}')

                new_params = ', '.join(typed_params)
            else:
                new_params = params

            # Determine return type
            if has_return_statement(func_body):
                return_type = " -> Any"
            else:
                return_type = " -> None"

            # Reconstruct line
            new_line = f'{indent}def {func_name}({new_params}){return_type}{space_before_colon}:{rest}'

            if new_line != line:
                lines[i] = new_line
                changes += 1

        i += 1

    return '\n'.join(lines), changes


def ensure_any_import(content: str) -> str:
    """Ensure 'Any' is imported from typing if needed."""
    if ' -> Any' not in content and ': Any' not in content:
        return content

    lines = content.split('\n')

    # Check if Any is already imported
    for line in lines:
        if 'from typing import' in line and 'Any' in line:
            return content

    # Find existing typing import line and add Any
    for i, line in enumerate(lines):
        # Only match module-level imports (no indentation)
        if line.startswith('from typing import'):
            # Check if it's already there
            if 'Any' in line:
                return content
            # Add Any to the import
            lines[i] = line.rstrip() + ', Any' if not line.endswith('import ') else line + 'Any'
            return '\n'.join(lines)

    # No typing import found, add one after docstring/module-level imports
    insert_pos = 0
    in_docstring = False
    found_imports = False

    for i, line in enumerate(lines):
        stripped = line.lstrip()

        # Track docstrings
        if stripped.startswith('"""') or stripped.startswith("'''"):
            in_docstring = not in_docstring
            if not in_docstring:
                insert_pos = i + 1
                continue

        # Only look at non-indented (module-level) code
        if not in_docstring and line and not line[0].isspace():
            if line.startswith('import ') or line.startswith('from '):
                found_imports = True
                insert_pos = i + 1
            elif found_imports:
                # We've passed the import section
                break

    lines.insert(insert_pos, 'from typing import Any')
    return '\n'.join(lines)


def process_file(file_path: Path) -> Tuple[bool, int]:
    """Process a single file to add type annotations."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Fix helper functions
        new_content, changes = fix_helper_function_annotations(content)

        if changes > 0:
            # Note: Assumes Any is already imported at module level
            # (should be pre-added before running this script)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return True, changes

        return False, 0

    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
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
