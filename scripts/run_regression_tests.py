"""Run the full regression test suite."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the regression test suite.")
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments passed to pytest.",
    )
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    from tests.regression_suite import build_pytest_args  # noqa: PLC0415

    raw_pytest_args = args.pytest_args
    if raw_pytest_args and raw_pytest_args[0] == "--":
        raw_pytest_args = raw_pytest_args[1:]

    pytest_args = build_pytest_args(raw_pytest_args)
    command = [sys.executable, "-m", "pytest", *pytest_args]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
