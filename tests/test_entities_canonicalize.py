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


@pytest.mark.parametrize(
    ("raw", "expected", "description"),
    [
        # Empty strings
        ("", "", "empty string"),
        ("   ", "", "whitespace only"),
        # Strings with only punctuation
        ("!!!", "", "only punctuation"),
        ("...", "", "only periods"),
        ("---", "", "only hyphens"),
        ("@#$%", "", "special characters"),
        # Strings with only suffixes
        ("LLC", "", "only LLC suffix"),
        ("Inc", "", "only Inc suffix"),
        ("Corp", "", "only Corp suffix"),
        ("Ltd", "", "only Ltd suffix"),
        ("LP", "", "only LP suffix"),
        # Multiple consecutive suffixes
        ("Company Inc. LLC", "company", "multiple suffixes"),
        ("Business Corp Ltd", "business", "multiple suffixes"),
        ("Property LP LLC Inc", "property", "multiple suffixes"),
        # Suffixes in the middle
        ("LLC Properties", "properties", "suffix at start"),
        ("Inc Real Estate", "real estate", "suffix at start"),
        ("Corp Holdings LLC", "holdings", "suffix at start and end"),
        # Unicode characters
        ("Café Inc", "caf", "unicode accent"),
        ("Naïve Corp", "nave", "unicode diaeresis"),
        ("Résumé LLC", "rsum", "unicode acute"),
        ("日本 Company", "company", "unicode CJK"),
        ("München GmbH", "mnchen gmbh", "unicode umlaut"),
        # Very long strings
        (
            "A" * 1000 + " Corp",
            "a" * 1000,
            "1000 character name",
        ),
        (
            "Very Long Company Name With Many Words And Spaces LLC",
            "very long company name with many words and spaces",
            "long multi-word name",
        ),
        # Mixed edge cases
        ("  !!!LLC!!!  ", "", "suffix surrounded by punctuation and spaces"),
        ("123 Inc 456", "123 456", "numbers with suffix in middle"),
        ("Corp-to-Corp LLC", "corptocorp", "suffix used as word and as suffix"),
    ],
)
def test_canonicalize_edge_cases(raw: str, expected: str, description: str) -> None:
    """Test edge cases for canonicalize function."""
    assert canonicalize(raw) == expected, f"Failed for: {description}"
