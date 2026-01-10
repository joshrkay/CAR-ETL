"""
OM field extraction with marketing-aware confidence scoring.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.extraction.normalizers import normalize_field_value
from src.extraction.om_confidence import (
    calculate_om_field_confidence,
    calculate_om_document_confidence,
    OMExtractedField,
    OM_FIELDS,
)
from src.extraction.om_fields import OMFieldDefinition
from src.extraction.om_prompts import build_om_extraction_prompt
from src.services.redaction import presidio_redact

AsyncOpenAIClient: type[Any] | None
try:
    from openai import AsyncOpenAI as _AsyncOpenAIClient
except ImportError:  # pragma: no cover - handled at runtime if dependency missing
    AsyncOpenAIClient = None
else:
    AsyncOpenAIClient = _AsyncOpenAIClient

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_LLM_MODEL = "gpt-4o-mini"


class OMExtractionResult(BaseModel):
    fields: Dict[str, OMExtractedField]
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    warnings: List[str] = Field(default_factory=list)
    missing_critical: List[str] = Field(default_factory=list)


class OMExtractor:
    """Extracts structured OM fields using RAG + LLM."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_LLM_MODEL):
        if AsyncOpenAIClient is None:
            raise ImportError("openai package is required for OM extraction. Please install openai>=1.0.0.")
        api_key = api_key or OPENAI_API_KEY
        if not api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        self.client = AsyncOpenAIClient(api_key=api_key)
        self.model = model

    async def extract_fields(self, document_text: str, rag_snippets: Optional[List[str]] = None) -> OMExtractionResult:
        """Extract OM fields with marketing-aware scoring."""
        rag_context = "\n\n".join(rag_snippets) if rag_snippets else ""
        combined_text = f"{document_text}\n\nRAG_CONTEXT:\n{rag_context}" if rag_context else document_text

        redacted_text = presidio_redact(combined_text)
        prompt = build_om_extraction_prompt(redacted_text, OM_FIELDS)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a CRE OM extraction assistant. Respond only with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
        except Exception as exc:
            logger.error("LLM extraction failed", extra={"error": str(exc)})
            raise

        try:
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("LLM response was missing content")
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("LLM response not JSON", extra={"content": response.choices[0].message.content})
            raise ValueError("LLM response was not valid JSON") from exc

        extracted_fields: Dict[str, OMExtractedField] = {}
        flat_values: Dict[str, float] = {}
        warnings = payload.get("warnings", []) or []
        missing_critical = payload.get("missing_critical", []) or []

        def _process_section(section: Dict[str, Any]) -> None:
            for fname, meta in section.items():
                if fname not in OM_FIELDS:
                    continue
                field_def: OMFieldDefinition = OM_FIELDS[fname]
                raw_value = meta.get("value")
                base_conf = min(meta.get("confidence", 0.0), 0.99)
                source_section = meta.get("source_section") or meta.get("source")  # tolerate alt keys
                value_type = meta.get("value_type")
                normalized = normalize_field_value(raw_value, field_def.type.value, field_def.values)
                if normalized is None:
                    continue
                field_conf = calculate_om_field_confidence(
                    fname,
                    base_conf,
                    source_section,
                    value_type,
                    flat_values,
                    OM_FIELDS,
                )
                extracted_fields[fname] = OMExtractedField(
                    name=fname,
                    value=normalized,
                    confidence=min(field_conf, 0.99),
                    source_section=source_section,
                    value_type=value_type,
                )
                if isinstance(normalized, (int, float)):
                    flat_values[fname] = float(normalized)

        for section_key in [
            "property_info",
            "financials_in_place",
            "financials_pro_forma",
            "rent_roll_summary",
            "debt_info",
            "transaction_info",
        ]:
            section_data = payload.get(section_key, {}) or {}
            _process_section(section_data)

        overall_confidence = calculate_om_document_confidence(list(extracted_fields.values()), OM_FIELDS)

        return OMExtractionResult(
            fields=extracted_fields,
            overall_confidence=min(overall_confidence, 0.99),
            warnings=warnings,
            missing_critical=missing_critical,
        )
