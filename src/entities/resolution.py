"""Entity resolution and merge utilities."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Optional, cast
from uuid import UUID

from pydantic import BaseModel
from supabase import Client

from src.audit.logger import AuditLogger
from src.entities.matching import EntityRecord, JsonValue, evaluate_entity_match
from src.exceptions import NotFoundError
from src.services.redaction import presidio_redact

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MergePlan:
    """Plan for merging two entities."""

    canonical: EntityRecord
    duplicate: EntityRecord
    canonical_documents: int
    duplicate_documents: int


class MergeResult(BaseModel):
    """Merge response payload."""

    merged_entity_id: UUID
    documents_updated: int


def fetch_entity_record(
    supabase: Client,
    tenant_id: UUID,
    entity_id: UUID,
) -> EntityRecord:
    """Fetch an entity record for the tenant."""
    result = (
        supabase.table("entities")
        .select("id, tenant_id, canonical_name, attributes, external_id, updated_at")
        .eq("id", str(entity_id))
        .eq("tenant_id", str(tenant_id))
        .limit(1)
        .execute()
    )

    if not result.data:
        raise NotFoundError(resource_type="Entity", resource_id=str(entity_id))

    record = result.data[0]
    attributes = record.get("attributes") or {}
    if not isinstance(attributes, dict):
        attributes = {}

    updated_at_raw = record.get("updated_at")
    if isinstance(updated_at_raw, str):
        updated_at = datetime.fromisoformat(updated_at_raw)
    else:
        updated_at = updated_at_raw

    return EntityRecord(
        id=UUID(record["id"]),
        tenant_id=UUID(record["tenant_id"]),
        canonical_name=record["canonical_name"],
        attributes=attributes,
        external_id=record.get("external_id"),
        updated_at=updated_at,
    )


def fetch_document_reference_count(
    supabase: Client,
    tenant_id: UUID,
    entity_id: UUID,
) -> int:
    """Count document references for an entity."""
    result = (
        supabase.table("entity_documents")
        .select("id")
        .eq("tenant_id", str(tenant_id))
        .eq("entity_id", str(entity_id))
        .execute()
    )
    return len(result.data or [])


def select_merge_plan(
    primary: EntityRecord,
    secondary: EntityRecord,
    primary_documents: int,
    secondary_documents: int,
) -> MergePlan:
    """Select canonical entity based on document references."""
    if primary_documents > secondary_documents:
        return MergePlan(primary, secondary, primary_documents, secondary_documents)
    if secondary_documents > primary_documents:
        return MergePlan(secondary, primary, secondary_documents, primary_documents)
    return MergePlan(primary, secondary, primary_documents, secondary_documents)


def merge_entity_attributes(
    canonical: EntityRecord,
    duplicate: EntityRecord,
) -> dict[str, JsonValue]:
    """
    Merge entity attributes using a "newer-wins" conflict resolution strategy.

    Attributes from the canonical entity are used as the base. For each key in the
    duplicate entity:

    * If the key is missing from the canonical attributes or the canonical value is
      ``None``, the duplicate value is copied over.
    * If both entities define the key with the same value, this is not treated as a
      conflict and the value is left unchanged.
    * If both entities define the key with different values, the value from the
      entity whose ``updated_at`` timestamp is more recent is preserved (i.e.,
      the newer record "wins" for that key).
    """
    merged: dict[str, JsonValue] = dict(canonical.attributes)
    canonical_newer = _is_newer_record(canonical.updated_at, duplicate.updated_at)

    for key, value in duplicate.attributes.items():
        if key not in merged or merged[key] is None:
            merged[key] = value
            continue
        if merged[key] == value:
            continue
        if not canonical_newer:
            merged[key] = value

    return merged


def redact_json_value(value: JsonValue) -> JsonValue:
    """Redact PII from JSON-like values."""
    if isinstance(value, str):
        return presidio_redact(value)
    if isinstance(value, list):
        return [redact_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_json_value(item) for key, item in value.items()}
    return value


def redact_entity_payload(
    canonical_name: str,
    attributes: dict[str, JsonValue],
) -> tuple[str, dict[str, JsonValue]]:
    """Redact entity payload fields before persistence."""
    redacted_name = presidio_redact(canonical_name)
    redacted_attributes_raw = redact_json_value(attributes)
    # redact_json_value preserves dict structure, safe to cast
    redacted_attributes = cast(dict[str, JsonValue], redacted_attributes_raw)
    return redacted_name, redacted_attributes


def update_entity_record(
    supabase: Client,
    entity: EntityRecord,
    attributes: dict[str, JsonValue],
) -> None:
    """Update entity record with merged attributes."""
    redacted_name, redacted_attributes = redact_entity_payload(
        entity.canonical_name,
        attributes,
    )
    payload = {
        "canonical_name": redacted_name,
        "attributes": redacted_attributes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = (
        supabase.table("entities")
        .update(payload)
        .eq("id", str(entity.id))
        .eq("tenant_id", str(entity.tenant_id))
        .execute()
    )
    if result.data is None:
        raise RuntimeError(
            f"Failed to update canonical entity id={entity.id}, tenant_id={entity.tenant_id}"
        )


def mark_entity_merged(
    supabase: Client,
    duplicate: EntityRecord,
    canonical_id: UUID,
) -> None:
    """Mark duplicate entity as merged while preserving attributes."""
    merged_attributes = dict(duplicate.attributes)
    merged_attributes["merge_status"] = "merged"
    merged_attributes["merged_into_id"] = str(canonical_id)
    merged_attributes["merged_at"] = datetime.now(timezone.utc).isoformat()

    _, redacted_attributes = redact_entity_payload(
        duplicate.canonical_name,
        merged_attributes,
    )

    result = (
        supabase.table("entities")
        .update({"attributes": redacted_attributes})
        .eq("id", str(duplicate.id))
        .eq("tenant_id", str(duplicate.tenant_id))
        .execute()
    )
    if result.data is None:
        raise RuntimeError("Failed to mark duplicate entity as merged")


def update_entity_document_references(
    supabase: Client,
    tenant_id: UUID,
    duplicate_id: UUID,
    canonical_id: UUID,
) -> int:
    """Update document references to point at the canonical entity."""
    canonical_id_str = str(canonical_id)
    duplicate_id_str = str(duplicate_id)
    result = (
        supabase.table("entity_documents")
        .update({"entity_id": canonical_id_str})
        .eq("tenant_id", str(tenant_id))
        .eq("entity_id", duplicate_id_str)
        .execute()
    )
    return len(result.data or [])


def record_duplicate_resolution(
    supabase: Client,
    tenant_id: UUID,
    entity_id_1: UUID,
    entity_id_2: UUID,
    match_score: float,
    reviewed_by: UUID,
) -> None:
    """Record a merge decision in entity_duplicates."""
    payload = {
        "tenant_id": str(tenant_id),
        "entity_id_1": str(entity_id_1),
        "entity_id_2": str(entity_id_2),
        "match_score": match_score,
        "status": "merged",
        "reviewed_by": str(reviewed_by),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    result = supabase.table("entity_duplicates").insert(payload).execute()
    if result.data is None:
        raise RuntimeError("Failed to record duplicate resolution")


def _is_newer_record(
    candidate: Optional[datetime],
    baseline: Optional[datetime],
) -> bool:
    if candidate and baseline:
        return candidate >= baseline
    if candidate and not baseline:
        return True
    return False


async def _log_merge_audit(
    audit_logger: AuditLogger,
    merge_plan: MergePlan,
    documents_updated: int,
    match_score: float,
) -> None:
    metadata = {
        "canonical_entity_id": str(merge_plan.canonical.id),
        "duplicate_entity_id": str(merge_plan.duplicate.id),
        "documents_updated": documents_updated,
        "match_score": match_score,
    }
    await audit_logger.log(
        event_type="entity.merge",
        action="update",
        resource_type="entity",
        resource_id=str(merge_plan.canonical.id),
        metadata=metadata,
    )


async def merge_entities(
    supabase: Client,
    tenant_id: UUID,
    source_entity_id: UUID,
    target_entity_id: UUID,
    reviewed_by: UUID,
    audit_logger: Optional[AuditLogger] = None,
) -> MergeResult:
    """Merge two entities and update references."""
    source_entity = fetch_entity_record(supabase, tenant_id, source_entity_id)
    target_entity = fetch_entity_record(supabase, tenant_id, target_entity_id)

    source_count = fetch_document_reference_count(supabase, tenant_id, source_entity_id)
    target_count = fetch_document_reference_count(supabase, tenant_id, target_entity_id)

    merge_plan = select_merge_plan(target_entity, source_entity, target_count, source_count)
    merged_attributes = merge_entity_attributes(merge_plan.canonical, merge_plan.duplicate)

    update_entity_record(supabase, merge_plan.canonical, merged_attributes)
    mark_entity_merged(supabase, merge_plan.duplicate, merge_plan.canonical.id)

    documents_updated = update_entity_document_references(
        supabase,
        tenant_id,
        merge_plan.duplicate.id,
        merge_plan.canonical.id,
    )

    match_result = evaluate_entity_match(source_entity, target_entity)
    record_duplicate_resolution(
        supabase,
        tenant_id,
        merge_plan.canonical.id,
        merge_plan.duplicate.id,
        match_result.score,
        reviewed_by,
    )

    if audit_logger:
        await _log_merge_audit(audit_logger, merge_plan, documents_updated, match_result.score)

    logger.info(
        "Entities merged",
        extra={
            "tenant_id": str(tenant_id),
            "canonical_entity_id": str(merge_plan.canonical.id),
            "duplicate_entity_id": str(merge_plan.duplicate.id),
            "documents_updated": documents_updated,
        },
    )

    return MergeResult(
        merged_entity_id=merge_plan.canonical.id,
        documents_updated=documents_updated,
    )
