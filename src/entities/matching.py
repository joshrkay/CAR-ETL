"""Entity matching utilities for deduplication."""
from __future__ import annotations

from difflib import SequenceMatcher
from enum import Enum
from typing import Optional, Any
from typing_extensions import TypeAlias
from uuid import UUID
from datetime import datetime
import re

from pydantic import BaseModel, Field


JsonPrimitive = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list[Any] | dict[str, Any]


class EntityRecord(BaseModel):
    """Entity record used for matching and resolution."""

    id: UUID = Field(..., description="Entity UUID")
    tenant_id: UUID = Field(..., description="Tenant UUID")
    canonical_name: str = Field(..., description="Canonical entity name")
    attributes: dict[str, JsonValue] = Field(default_factory=dict, description="Entity attributes")
    external_id: Optional[str] = Field(None, description="External system identifier")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class MatchDecision(str, Enum):
    """Match resolution decision."""

    AUTO_MERGE = "auto_merge"
    SUGGEST_MERGE = "suggest_merge"
    DIFFERENT = "different"


class MatchResult(BaseModel):
    """Match evaluation result."""

    score: float = Field(..., ge=0.0, le=1.0, description="Match score")
    decision: MatchDecision = Field(..., description="Resolution decision")


def normalize_text(value: str) -> str:
    """Normalize text for fuzzy comparison."""
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", normalized)


def calculate_similarity(value1: str, value2: str) -> float:
    """Calculate a similarity ratio between two strings."""
    if not value1 and not value2:
        return 1.0
    if not value1 or not value2:
        return 0.0
    return SequenceMatcher(None, value1, value2).ratio()


def compare_addresses(address1: str, address2: str) -> float:
    """Compare two addresses using fuzzy similarity."""
    normalized1 = normalize_text(address1)
    normalized2 = normalize_text(address2)
    return calculate_similarity(normalized1, normalized2)


def calculate_match_score(entity1: EntityRecord, entity2: EntityRecord) -> float:
    """Calculate match score for two entities."""
    score = 0.0
    max_score = 0.0

    # Name similarity always contributes; canonical_name is required
    name_similarity = calculate_similarity(
        normalize_text(entity1.canonical_name),
        normalize_text(entity2.canonical_name),
    )
    name_weight = 0.5
    max_score += name_weight
    score += name_similarity * name_weight

    # Address similarity only considered when both entities have an address string
    address1 = entity1.attributes.get("address")
    address2 = entity2.attributes.get("address")
    address_weight = 0.3
    if isinstance(address1, str) and isinstance(address2, str):
        address_similarity = compare_addresses(address1, address2)
        max_score += address_weight
        score += address_similarity * address_weight

    # External ID contributes only when both IDs are present; a mismatch reduces the
    # maximum achievable raw score, reflecting a conflict.
    external_id_weight = 0.2
    if entity1.external_id is not None and entity2.external_id is not None:
        max_score += external_id_weight
        if entity1.external_id == entity2.external_id:
            score += external_id_weight

    if max_score <= 0.0:
        normalized_score = 0.0
    else:
        normalized_score = score / max_score

    return min(normalized_score, 1.0)
def classify_match_score(score: float) -> MatchDecision:
    """Classify match score into resolution decision."""
    if score >= 0.95:
        return MatchDecision.AUTO_MERGE
    if score >= 0.80:
        return MatchDecision.SUGGEST_MERGE
    return MatchDecision.DIFFERENT


def evaluate_entity_match(entity1: EntityRecord, entity2: EntityRecord) -> MatchResult:
    """Evaluate entity match with score and decision."""
    score = calculate_match_score(entity1, entity2)
    decision = classify_match_score(score)
    return MatchResult(score=score, decision=decision)
