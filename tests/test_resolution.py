"""Tests for entity matching and resolution."""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.entities.matching import (
    EntityRecord,
    MatchDecision,
    calculate_match_score,
    classify_match_score,
    compare_addresses,
    normalize_text,
)
from src.entities.resolution import (
    fetch_document_reference_count,
    fetch_entity_record,
    merge_entities,
    merge_entity_attributes,
    redact_json_value,
    select_merge_plan,
)
from src.exceptions import NotFoundError


def _build_query_mock(data):
    query = MagicMock()
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value = MagicMock(data=data)
    return query


def _build_update_query_mock(data):
    query = MagicMock()
    query.eq.return_value = query
    query.execute.return_value = MagicMock(data=data)
    return query


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("  123 Main St. ") == "123 main st"


def test_compare_addresses_exact_match() -> None:
    assert compare_addresses("123 Main St", "123 Main St") == 1.0


def test_calculate_match_score_full_match() -> None:
    tenant_id = uuid4()
    entity1 = EntityRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        canonical_name="Acme Holdings",
        attributes={"address": "123 Main St"},
        external_id="EXT-1",
    )
    entity2 = EntityRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        canonical_name="Acme Holdings",
        attributes={"address": "123 Main St"},
        external_id="EXT-1",
    )

    assert calculate_match_score(entity1, entity2) == 1.0


def test_classify_match_score_thresholds() -> None:
    assert classify_match_score(0.95) == MatchDecision.AUTO_MERGE
    assert classify_match_score(0.80) == MatchDecision.SUGGEST_MERGE
    assert classify_match_score(0.79) == MatchDecision.DIFFERENT


def test_merge_entity_attributes_prefers_newer() -> None:
    tenant_id = uuid4()
    older = EntityRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        canonical_name="Alpha",
        attributes={"address": "Old", "phone": "111"},
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    newer = EntityRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        canonical_name="Alpha",
        attributes={"address": "New", "email": "a@example.com"},
        updated_at=datetime(2024, 2, 1, tzinfo=UTC),
    )

    merged = merge_entity_attributes(older, newer)

    assert merged["address"] == "New"
    assert merged["phone"] == "111"
    assert merged["email"] == "a@example.com"


def test_select_merge_plan_prefers_higher_document_count() -> None:
    tenant_id = uuid4()
    entity_primary = EntityRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        canonical_name="Primary",
        attributes={},
    )
    entity_secondary = EntityRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        canonical_name="Secondary",
        attributes={},
    )

    plan = select_merge_plan(entity_primary, entity_secondary, 5, 2)

    assert plan.canonical == entity_primary
    assert plan.duplicate == entity_secondary


def test_redact_json_value_redacts_strings() -> None:
    with patch("src.entities.resolution.presidio_redact", return_value="[REDACTED]"):
        result = redact_json_value({"name": "John Doe", "tags": ["ACME"]})

    assert result == {"name": "[REDACTED]", "tags": ["[REDACTED]"]}


def test_fetch_entity_record_not_found() -> None:
    supabase = MagicMock()
    entities_table = MagicMock()
    entities_table.select.return_value = _build_query_mock([])
    supabase.table.return_value = entities_table

    with pytest.raises(NotFoundError):
        fetch_entity_record(supabase, uuid4(), uuid4())


def test_fetch_document_reference_count_returns_count() -> None:
    supabase = MagicMock()
    documents_table = MagicMock()
    documents_table.select.return_value = _build_query_mock([{"id": "1"}, {"id": "2"}])
    supabase.table.return_value = documents_table

    count = fetch_document_reference_count(supabase, uuid4(), uuid4())

    assert count == 2


@pytest.mark.asyncio
async def test_merge_entities_updates_references():
    tenant_id = uuid4()
    user_id = uuid4()
    source_id = uuid4()
    target_id = uuid4()

    source_record = {
        "id": str(source_id),
        "tenant_id": str(tenant_id),
        "canonical_name": "Source",
        "attributes": {"address": "A"},
        "external_id": "EXT-1",
        "updated_at": datetime(2024, 1, 1, tzinfo=UTC).isoformat(),
    }
    target_record = {
        "id": str(target_id),
        "tenant_id": str(tenant_id),
        "canonical_name": "Target",
        "attributes": {"address": "B"},
        "external_id": "EXT-1",
        "updated_at": datetime(2024, 2, 1, tzinfo=UTC).isoformat(),
    }

    supabase = MagicMock()

    entities_select_source = MagicMock()
    entities_select_source.select.return_value = _build_query_mock([source_record])

    entities_select_target = MagicMock()
    entities_select_target.select.return_value = _build_query_mock([target_record])

    documents_select_source = MagicMock()
    documents_select_source.select.return_value = _build_query_mock([{"id": "doc1"}])

    documents_select_target = MagicMock()
    documents_select_target.select.return_value = _build_query_mock([{"id": "doc1"}, {"id": "doc2"}])

    entities_update_canonical = MagicMock()
    entities_update_canonical.update.return_value = _build_update_query_mock([{"id": str(target_id)}])

    entities_update_duplicate = MagicMock()
    entities_update_duplicate.update.return_value = _build_update_query_mock([{"id": str(source_id)}])

    documents_update = MagicMock()
    documents_update.update.return_value = _build_update_query_mock([{"id": "doc1"}])

    duplicates_insert = MagicMock()
    duplicates_insert.insert.return_value = MagicMock(execute=MagicMock(return_value=MagicMock(data=[{"id": "dup"}])))

    supabase.table.side_effect = [
        entities_select_source,
        entities_select_target,
        documents_select_source,
        documents_select_target,
        entities_update_canonical,
        entities_update_duplicate,
        documents_update,
        duplicates_insert,
    ]

    with patch("src.entities.resolution.presidio_redact", side_effect=lambda value: value):
        result = await merge_entities(
            supabase=supabase,
            tenant_id=tenant_id,
            source_entity_id=source_id,
            target_entity_id=target_id,
            reviewed_by=user_id,
            audit_logger=None,
        )

    assert result.merged_entity_id == target_id
    assert result.documents_updated == 1
