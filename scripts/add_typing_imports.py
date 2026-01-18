#!/usr/bin/env python3
"""
Safely add typing.Any import to test files.

Handles:
- Existing typing imports (single and multi-line)
- Module-level vs class-level positioning
- Preserves formatting
"""

import ast
import sys
from pathlib import Path


def add_any_import(file_path: Path) -> bool:
    """Add typing.Any import to a file if not present."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse to check syntax and find imports
        tree = ast.parse(content)

        # Check if Any is already imported
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == 'typing':
                    names = [alias.name for alias in node.names]
                    if 'Any' in names or '*' in names:
                        return False  # Already has Any

        # Find where to insert/modify
        lines = content.split('\n')
        typing_import_line = None
        last_import_line = None

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('from typing import'):
                typing_import_line = i
                # Check if this is a multi-line import
                if '(' in line and ')' not in line:
                    # Multi-line import, find the closing
                    j = i + 1
                    while j < len(lines) and ')' not in lines[j]:
                        j += 1
                    # Add Any before the closing paren
                    lines[j] = lines[j].replace(')', ', Any)')
                    typing_import_line = None  # Mark as handled
                    break
                else:
                    # Single line import
                    break
            elif (stripped.startswith('from ') or stripped.startswith('import ')) and not line.startswith(' '):
                last_import_line = i

        # Modify or insert
        if typing_import_line is not None:
            # Add Any to existing single-line import
            line = lines[typing_import_line]
            if line.endswith(')'):
                lines[typing_import_line] = line[:-1] + ', Any)'
            else:
                lines[typing_import_line] = line.rstrip() + ', Any'
        elif last_import_line is not None:
            # Insert new typing import after last import
            lines.insert(last_import_line + 1, 'from typing import Any')
        else:
            # No imports found, add after docstring if exists
            insert_pos = 0
            in_docstring = False
            for i, line in enumerate(lines):
                if '"""' in line or "'''" in line:
                    if in_docstring:
                        insert_pos = i + 1
                        break
                    in_docstring = True

            if insert_pos == 0:
                # Add at top after module docstring
                lines.insert(0, 'from typing import Any\n')
            else:
                lines.insert(insert_pos, '\nfrom typing import Any')

        new_content = '\n'.join(lines)

        # Validate syntax
        try:
            ast.parse(new_content)
        except SyntaxError as e:
            print(f"  ⚠ Syntax error after modification in {file_path.name}: {e}")
            return False

        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return True

    except Exception as e:
        print(f"  ✗ Error processing {file_path.name}: {e}")
        return False


def main() -> None:
    """Process all test files."""
    tests_dir = Path('tests')
    if not tests_dir.exists():
        print("tests/ directory not found")
        sys.exit(1)

    test_files = sorted(tests_dir.glob('test_*.py'))
    modified = 0

    print(f"Adding typing.Any imports to {len(test_files)} files...")

    for file_path in test_files:
        if add_any_import(file_path):
            print(f"  ✓ {file_path.name}")
            modified += 1

    print(f"\nModified {modified}/{len(test_files)} files")


if __name__ == '__main__':
    main()
