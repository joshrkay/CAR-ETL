"""Tests for entity canonicalization."""

import pytest

from src.entities.canonicalize import canonicalize


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Acme Corp LLC", "acme"),
        ("  Downtown Properties, Inc.  ", "downtown properties"),
        ("123 Main St. LP", "123 main st"),
        ("Tenant-Landlord, Ltd", "tenantlandlord"),
    ],
)
def test_canonicalize_normalizes_name(raw: str, expected: str) -> None:
    """Canonicalize strips punctuation, casing, and suffixes."""
    assert canonicalize(raw) == expected
