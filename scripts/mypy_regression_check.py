#!/usr/bin/env python3
"""
Mypy Regression Testing Suite

This script helps ensure that mypy fixes don't introduce new issues by:
1. Capturing a baseline of current mypy errors
2. Running tests to verify functionality
3. Comparing before/after states

Usage:
    python scripts/mypy_regression_check.py baseline  # Create baseline
    python scripts/mypy_regression_check.py check     # Check for regressions
"""

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


class MypyRegressionChecker:
    def __init__(self) -> None:
        self.baseline_file = Path("mypy_baseline.json")
        self.current_errors_file = Path("mypy_current.txt")

    def run_mypy(self) -> str:
        """Run mypy and return the output.

        Note: Clears mypy cache before running to avoid stale cache issues.
        """
        # Clear mypy cache to avoid false positives from stale cache
        cache_dir = Path(".mypy_cache")
        if cache_dir.exists():
            import shutil
            shutil.rmtree(cache_dir, ignore_errors=True)

        result = subprocess.run(
            ["python", "-m", "mypy", "src", "tests"],
            capture_output=True,
            text=True
        )
        return result.stdout + result.stderr

    def parse_mypy_output(self, output: str) -> dict[str, list[dict[str, str]]]:
        """Parse mypy output into structured format."""
        errors_by_type: dict[str, list[dict[str, str]]] = defaultdict(list)

        for line in output.split('\n'):
            if 'error:' in line:
                # Parse: file:line: error: message [error-code]
                parts = line.split('error:', 1)
                if len(parts) == 2:
                    location = parts[0].strip()
                    message_part = parts[1].strip()

                    # Extract error code
                    error_code = "unknown"
                    if '[' in message_part and ']' in message_part:
                        error_code = message_part.split('[')[-1].split(']')[0]

                    errors_by_type[error_code].append({
                        'location': location,
                        'message': message_part
                    })

        return errors_by_type

    def create_baseline(self) -> None:
        """Create a baseline of current mypy errors."""
        print("Creating mypy baseline...")
        output = self.run_mypy()

        # Save raw output
        with open('mypy_baseline.txt', 'w') as f:
            f.write(output)

        # Parse and save structured data
        errors_by_type = self.parse_mypy_output(output)

        baseline_data = {
            'total_errors': sum(len(errors) for errors in errors_by_type.values()),
            'errors_by_type': {k: len(v) for k, v in errors_by_type.items()},
            'full_errors': dict(errors_by_type)
        }

        with open(self.baseline_file, 'w') as f:
            json.dump(baseline_data, f, indent=2)

        print("\nBaseline created:")
        print(f"  Total errors: {baseline_data['total_errors']}")
        print("  Error types:")
        for error_type, count in sorted(baseline_data['errors_by_type'].items(),
                                       key=lambda x: x[1], reverse=True):
            print(f"    {error_type}: {count}")

        print(f"\nBaseline saved to {self.baseline_file}")

    def check_regressions(self) -> bool:
        """Check for regressions compared to baseline."""
        if not self.baseline_file.exists():
            print("Error: No baseline found. Run 'baseline' command first.")
            return False

        print("Checking for mypy regressions...")

        # Load baseline
        with open(self.baseline_file) as f:
            baseline = json.load(f)

        # Run current mypy
        output = self.run_mypy()
        with open(self.current_errors_file, 'w') as f:
            f.write(output)

        current_errors = self.parse_mypy_output(output)
        current_totals = {k: len(v) for k, v in current_errors.items()}
        total_current = sum(current_totals.values())

        # Compare
        print("\nComparison:")
        print(f"  Baseline errors: {baseline['total_errors']}")
        print(f"  Current errors:  {total_current}")

        if total_current > baseline['total_errors']:
            print(f"  ❌ REGRESSION: {total_current - baseline['total_errors']} new errors!")
            has_regression = True
        elif total_current < baseline['total_errors']:
            print(f"  ✅ IMPROVEMENT: {baseline['total_errors'] - total_current} fewer errors!")
            has_regression = False
        else:
            print("  ✓ No change in error count")
            has_regression = False

        # Show changes by error type
        all_error_types = set(baseline['errors_by_type'].keys()) | set(current_totals.keys())
        print("\nChanges by error type:")

        for error_type in sorted(all_error_types):
            baseline_count = baseline['errors_by_type'].get(error_type, 0)
            current_count = current_totals.get(error_type, 0)
            diff = current_count - baseline_count

            if diff != 0:
                symbol = "❌" if diff > 0 else "✅"
                sign = "+" if diff > 0 else ""
                print(f"  {symbol} {error_type}: {baseline_count} -> {current_count} ({sign}{diff})")

        # Run tests
        print("\n" + "="*60)
        print("Running pytest to ensure no functional regressions...")
        print("="*60)

        test_result = subprocess.run(
            ["python", "-m", "pytest", "-v", "--tb=short"],
            capture_output=False
        )

        if test_result.returncode != 0:
            print("\n❌ Tests failed! There may be functional regressions.")
            has_regression = True
        else:
            print("\n✅ All tests passed!")

        return not has_regression

    def summary(self) -> None:
        """Show summary of current state."""
        if not self.baseline_file.exists():
            print("No baseline found. Run 'baseline' command first.")
            return

        with open(self.baseline_file) as f:
            baseline = json.load(f)

        print("Mypy Error Summary")
        print("="*60)
        print(f"Total errors: {baseline['total_errors']}")
        print("\nBreakdown by error type:")

        for error_type, count in sorted(baseline['errors_by_type'].items(),
                                       key=lambda x: x[1], reverse=True):
            print(f"  {error_type:30s} {count:4d}")


def main() -> None:
    checker = MypyRegressionChecker()

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "baseline":
        checker.create_baseline()
    elif command == "check":
        success = checker.check_regressions()
        sys.exit(0 if success else 1)
    elif command == "summary":
        checker.summary()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
