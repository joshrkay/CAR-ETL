"""Reusable regression test suite definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence


TEST_FILE_GLOB = "test_*.py"


def get_regression_test_paths(test_root: Path | None = None) -> List[str]:
    """Return sorted list of regression test file paths."""
    root = test_root or Path(__file__).resolve().parent
    return [str(path) for path in sorted(root.glob(TEST_FILE_GLOB))]


def build_pytest_args(extra_args: Sequence[str] | None = None) -> List[str]:
    """Build pytest arguments for the full regression suite."""
    args: List[str] = get_regression_test_paths()
    if extra_args:
        args.extend(extra_args)
    return args


def iter_regression_tests(test_root: Path | None = None) -> Iterable[Path]:
    """Yield regression test files for external tooling."""
    root = test_root or Path(__file__).resolve().parent
    yield from sorted(root.glob(TEST_FILE_GLOB))
