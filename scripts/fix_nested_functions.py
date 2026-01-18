#!/usr/bin/env python3
"""
Enhanced script to fix ALL missing type annotations in test files.

Handles:
- Helper functions (module-level)
- Nested functions (closures, factories)
- Route handlers (@app.get, @app.post, etc.)
- Test method parameters (fixtures)
- Async functions
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


def has_return_statement(func_body: str) -> bool:
    """Check if function has any return statements with values."""
    return bool(re.search(r'return\s+(?!None\s*$)(?!$).+', func_body))


def split_params(params: str) -> List[str]:
    """Split function parameters by comma, respecting bracket nesting."""
    if not params.strip():
        return []

    result = []
    current = []
    depth = 0

    for char in params:
        if char in '([{':
            depth += 1
            current.append(char)
        elif char in ')]}':
            depth -= 1
            current.append(char)
        elif char == ',' and depth == 0:
            result.append(''.join(current).strip())
            current = []
        else:
            current.append(char)

    if current:
        result.append(''.join(current).strip())

    return result


def infer_param_type(param_name: str, func_body: str, context: str = "") -> str:
    """Infer parameter type from usage patterns and context."""
    safe_param = re.escape(param_name)

    try:
        if re.search(rf'\b{safe_param}\s*==\s*["\']', func_body):
            return "str"
        elif re.search(rf'\b{safe_param}\s*==\s*\d+', func_body):
            return "int"
        elif re.search(rf'\b{safe_param}\s*==\s*(True|False)', func_body):
            return "bool"
        elif re.search(rf'\[{safe_param}\]', func_body):
            return "str"
    except re.error:
        pass

    # Context-based heuristics
    if "fixture" in context.lower():
        return "Any"  # Fixtures are usually Any
    if any(word in param_name.lower() for word in ["client", "mock", "app", "config", "token"]):
        return "Any"

    return "Any"


def is_route_decorator(line: str) -> bool:
    """Check if line is a route decorator (@app.get, @app.post, etc.)."""
    return bool(re.search(r'@\w+\.(get|post|put|delete|patch|options|head)\(', line))


def fix_nested_and_route_functions(content: str) -> Tuple[str, int]:
    """Add type annotations to nested functions and route handlers."""
    lines = content.split('\n')
    changes = 0
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for route decorators
        is_route = is_route_decorator(line)

        # Check if next line(s) contain a function definition
        j = i + 1
        while j < len(lines) and (lines[j].strip().startswith('@') or not lines[j].strip()):
            if is_route_decorator(lines[j]):
                is_route = True
            j += 1

        if j < len(lines):
            func_line = lines[j]

            # Check if this is a multi-line function definition
            # Only check for multi-line if this line contains 'def ' and is incomplete
            # A complete single-line has both ')' and ':' even if separated by '-> Type'
            if 'def ' in func_line and '(' in func_line and not (')' in func_line and ':' in func_line):
                # Multi-line function definition - collect all lines until closing ): or ->
                func_lines = [func_line]
                k = j + 1
                while k < len(lines) and '):' not in lines[k] and '->' not in lines[k]:
                    func_lines.append(lines[k])
                    k += 1
                if k < len(lines):
                    func_lines.append(lines[k])  # Line with closing ): or ->

                # Process multi-line function parameters by adding types inline
                # Handle lines with multiple comma-separated parameters
                made_changes = False
                for line_idx in range(len(func_lines)):
                    line = func_lines[line_idx]
                    # Skip the first line (has function name) and last line (has ): or ->)
                    if line_idx == 0 or line_idx == len(func_lines) - 1:
                        continue

                    stripped = line.strip()
                    if not stripped or stripped.startswith('#'):
                        continue

                    # Split by comma to handle multiple parameters per line
                    indent_match = re.match(r'^(\s*)', line)
                    indent = indent_match.group(1) if indent_match else '    '

                    # Handle multiple params on one line: "param1, param2, param3: Type"
                    if ',' in stripped:
                        # Check if original line has trailing comma
                        has_trailing_comma = stripped.endswith(',')

                        # Split carefully
                        params_on_line = split_params(stripped)
                        new_params = []
                        line_modified = False

                        for param in params_on_line:
                            param = param.strip()
                            if not param or param == 'self':
                                if param:  # Only add non-empty
                                    new_params.append(param)
                            elif ':' in param:
                                new_params.append(param)
                            elif '=' in param and ':' not in param:
                                # Has default but no type
                                param_name = param.split('=')[0].strip()
                                default_part = param.split('=', 1)[1].strip()
                                new_params.append(f'{param_name}: Any = {default_part}')
                                line_modified = True
                            else:
                                # No type, no default
                                new_params.append(f'{param}: Any')
                                line_modified = True

                        if line_modified:
                            # Reconstruct the line, preserving trailing comma
                            new_line = f'{indent}{", ".join(new_params)}'
                            if has_trailing_comma:
                                new_line += ','
                            if line.endswith('\n'):
                                new_line += '\n'
                            func_lines[line_idx] = new_line
                            made_changes = True
                    else:
                        # Single parameter on this line
                        # Check for comma BEFORE stripping it
                        has_comma = stripped.endswith(',')
                        param_text = stripped.rstrip(',').strip()

                        if param_text and param_text != 'self':
                            if ':' not in param_text and '=' not in param_text:
                                # Simple parameter without type - add : Any
                                func_lines[line_idx] = f'{indent}{param_text}: Any{"," if has_comma else ""}\n' if line.endswith('\n') else f'{indent}{param_text}: Any{"," if has_comma else ""}'
                                made_changes = True
                            elif '=' in param_text and ':' not in param_text:
                                # Parameter with default but no type - add : Any before =
                                param_name = param_text.split('=')[0].strip()
                                default_part = param_text.split('=', 1)[1]
                                func_lines[line_idx] = f'{indent}{param_name}: Any = {default_part}{"," if has_comma else ""}\n' if line.endswith('\n') else f'{indent}{param_name}: Any = {default_part}{"," if has_comma else ""}'
                                made_changes = True

                if made_changes:
                    # Write back the modified lines
                    for idx, updated_line in enumerate(func_lines):
                        lines[j + idx] = updated_line
                    changes += 1

                # Check if return type needs to be added (route handlers)
                last_line = func_lines[-1]
                if '->' not in last_line and is_route:
                    if last_line.strip() == '):':
                        func_lines[-1] = last_line.replace('):', ') -> Any:')
                        for idx, updated_line in enumerate(func_lines):
                            lines[j + idx] = updated_line
                        changes += 1

                i = k  # Skip past this multi-line function
                continue

            # Match single-line function definitions (with or without return type)
            match = re.match(r'^(\s*)(async\s+)?def\s+(\w+)\((.*?)\)(\s*)(->.*?)?:(.*)$', func_line)

            if match:
                indent = match.group(1)
                async_kw = match.group(2) or ''
                func_name = match.group(3)
                params = match.group(4)
                space_before_arrow = match.group(5)
                existing_return = match.group(6)  # Might be None or " -> Type"
                rest = match.group(7)

                # Determine if this needs fixing
                needs_return_type = existing_return is None or existing_return.strip() == '->'
                needs_param_types = False

                # Detect function context
                is_nested = len(indent) > 4  # More than class method indent
                is_test_method = func_name.startswith('test_')

                # Pre-check parameters to see if any lack type annotations
                if params.strip():
                    param_list = split_params(params)
                    for param in param_list:
                        if ':' not in param and param != 'self':
                            needs_param_types = True
                            break

                # Process if: route handler, nested function, OR has untyped params/return
                # This includes test methods with untyped fixture parameters
                should_process = is_route or is_nested or needs_param_types or needs_return_type

                if should_process:
                    # Collect function body for analysis
                    func_body_lines = []
                    k = j + 1
                    if k < len(lines):
                        func_indent_match = re.match(r'^(\s+)', lines[k])
                        if func_indent_match:
                            func_indent = func_indent_match.group(1)
                            while k < len(lines):
                                if lines[k].strip() and not lines[k].startswith(func_indent) and not lines[k].startswith(indent + '    '):
                                    break
                                func_body_lines.append(lines[k])
                                k += 1

                    func_body = '\n'.join(func_body_lines)

                    # Process parameters - check if any lack type annotations
                    if params.strip():
                        param_list = split_params(params)
                        typed_params = []

                        for param in param_list:
                            if ':' in param or param == 'self':
                                typed_params.append(param)
                            else:
                                needs_param_types = True
                                param_name = param.split('=')[0].strip()
                                param_type = infer_param_type(param_name, func_body)

                                if '=' in param:
                                    default_val = param.split('=', 1)[1].strip()
                                    typed_params.append(f'{param_name}: {param_type} = {default_val}')
                                else:
                                    typed_params.append(f'{param_name}: {param_type}')

                        new_params = ', '.join(typed_params)
                    else:
                        new_params = params

                    # Determine return type if needed
                    if needs_return_type:
                        if is_route or has_return_statement(func_body):
                            return_type = " -> Any"
                        else:
                            return_type = " -> None"
                    else:
                        return_type = existing_return

                    # Only reconstruct if changes needed
                    if needs_return_type or needs_param_types:
                        # Reconstruct line with proper spacing
                        new_line = f'{indent}{async_kw}def {func_name}({new_params}) {return_type.strip()}:{rest}'

                        if new_line != lines[j]:
                            lines[j] = new_line
                            changes += 1

        i += 1

    return '\n'.join(lines), changes


def fix_fixture_parameters(content: str) -> Tuple[str, int]:
    """Add type annotations to fixture parameters in test methods."""
    lines = content.split('\n')
    changes = 0

    for i, line in enumerate(lines):
        # Match test method definitions with parameters
        match = re.match(r'^(\s+)def\s+(test_\w+)\(self,\s*([^)]+)\)(\s*)(->.*)?:', line)
        if match and not match.group(5):  # No return type yet (should have -> None)
            indent = match.group(1)
            func_name = match.group(2)
            params = match.group(3)
            space = match.group(4)

            # Process parameters - add : Any to those without types
            param_list = split_params(params)
            typed_params = []

            for param in param_list:
                if ':' in param:
                    typed_params.append(param)
                else:
                    param_name = param.split('=')[0].strip()
                    if '=' in param:
                        default_val = param.split('=', 1)[1].strip()
                        typed_params.append(f'{param_name}: Any = {default_val}')
                    else:
                        typed_params.append(f'{param_name}: Any')

            new_params = ', '.join(typed_params)
            new_line = f'{indent}def {func_name}(self, {new_params}){space}) -> None:'

            if new_line != line:
                lines[i] = new_line
                changes += 1

    return '\n'.join(lines), changes


def process_file(file_path: Path) -> Tuple[bool, int]:
    """Process a single file to add all missing type annotations."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        total_changes = 0

        # Fix nested functions and route handlers
        content, changes1 = fix_nested_and_route_functions(content)
        total_changes += changes1

        # Fix fixture parameters in test methods
        content, changes2 = fix_fixture_parameters(content)
        total_changes += changes2

        if total_changes > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, total_changes

        return False, 0

    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False, 0


def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
        if not file_path.exists():
            print(f"File not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        test_files = [file_path]
    else:
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
