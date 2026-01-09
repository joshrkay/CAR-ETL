"""
Field Extractor - Understanding Plane

Extracts structured fields from documents using LLM.
Handles document type detection, field extraction, and normalization.
"""

import json
import logging
import os
from typing import Dict, Any, Optional

try:
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover - handled in runtime environments without openai
    AsyncOpenAI = None  # type: ignore
from pydantic import BaseModel, Field

from src.extraction.cre_fields import get_field_config, get_field_definitions_for_prompt
from src.extraction.prompts import build_extraction_prompt, build_document_type_detection_prompt
from src.extraction.normalizers import normalize_field_value
from src.services.redaction import presidio_redact

logger = logging.getLogger(__name__)

# OpenAI API key from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_LLM_MODEL = "gpt-4o-mini"


class ExtractedField(BaseModel):
    """Single extracted field with metadata."""
    value: Any = Field(None, description="Extracted value (normalized)")
    confidence: float = Field(..., ge=0.0, le=0.99, description="Confidence score (never 1.0)")
    page: Optional[int] = Field(None, ge=1, description="Page number where found")
    quote: Optional[str] = Field(None, description="Supporting text quote")


class ExtractionResult(BaseModel):
    """Result of field extraction."""
    fields: Dict[str, ExtractedField] = Field(..., description="Extracted fields")
    document_type: str = Field(..., description="Detected document type")
    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence")


class FieldExtractor:
    """
    Extracts structured fields from documents using LLM.
    
    Handles:
    - Document type detection
    - Industry-specific field extraction
    - Value normalization
    - Confidence calculation
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_LLM_MODEL):
        """
        Initialize field extractor.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: LLM model to use (default: gpt-4o-mini)
        """
        if AsyncOpenAI is None:
            raise ImportError("openai package is required for extraction. Please install openai>=1.0.0.")
        api_key = api_key or OPENAI_API_KEY
        if not api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def detect_document_type(
        self,
        document_text: str,
        industry: str
    ) -> Dict[str, Any]:
        """
        Detect document type from first page.
        
        Args:
            document_text: Document text (first page will be used)
            industry: Industry identifier (e.g., 'cre')
            
        Returns:
            Dictionary with document_type, confidence, and reasoning
        """
        # Use first 2000 characters for detection
        first_page_text = document_text[:2000]
        
        # SECURITY: Redact before sending to LLM
        redacted_text = presidio_redact(first_page_text)
        
        prompt = build_document_type_detection_prompt(redacted_text, industry)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a document classification assistant. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            return {
                "document_type": result.get("document_type", "other"),
                "confidence": min(result.get("confidence", 0.5), 0.99),  # Never 1.0
                "reasoning": result.get("reasoning", "")
            }
        except Exception as e:
            logger.error(
                "Failed to detect document type",
                extra={"industry": industry, "error": str(e)},
                exc_info=True
            )
            return {
                "document_type": "other",
                "confidence": 0.0,
                "reasoning": f"Detection failed: {str(e)}"
            }
    
    async def extract_fields(
        self,
        document_text: str,
        industry: str,
        document_type: str
    ) -> ExtractionResult:
        """
        Extract fields from document.
        
        Args:
            document_text: Full document text
            industry: Industry identifier (e.g., 'cre')
            document_type: Document type (e.g., 'lease')
            
        Returns:
            ExtractionResult with extracted fields and confidence
        """
        # Get field definitions for industry and document type
        field_defs = get_field_config(industry, document_type)
        field_definitions_str = get_field_definitions_for_prompt(field_defs)
        
        # SECURITY: Redact before sending to LLM
        redacted_text = presidio_redact(document_text)
        
        # Build prompt
        prompt = build_extraction_prompt(
            field_definitions_str,
            redacted_text,
            industry,
            document_type
        )
        
        # Call LLM
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a document extraction assistant. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            llm_result = json.loads(response.choices[0].message.content)
            raw_fields = llm_result.get("fields", {})
            
            # Normalize and process fields
            extracted_fields: Dict[str, ExtractedField] = {}
            
            for field_name, raw_field in raw_fields.items():
                if field_name not in field_defs:
                    continue
                
                field_def = field_defs[field_name]
                raw_value = raw_field.get("value")
                confidence = min(raw_field.get("confidence", 0.0), 0.99)  # Never 1.0
                page = raw_field.get("page")
                quote = raw_field.get("quote")
                
                # Normalize value
                normalized_value = normalize_field_value(
                    raw_value,
                    field_def.type.value,
                    field_def.values
                )
                
                extracted_fields[field_name] = ExtractedField(
                    value=normalized_value,
                    confidence=confidence,
                    page=page,
                    quote=quote
                )
            
            # Compute overall confidence
            overall_confidence = self._compute_overall_confidence(
                extracted_fields,
                field_defs
            )
            
            return ExtractionResult(
                fields=extracted_fields,
                document_type=document_type,
                overall_confidence=overall_confidence
            )
            
        except Exception as e:
            logger.error(
                "Failed to extract fields",
                extra={
                    "industry": industry,
                    "document_type": document_type,
                    "error": str(e)
                },
                exc_info=True
            )
            raise
    
    def _compute_overall_confidence(
        self,
        fields: Dict[str, ExtractedField],
        field_defs: Dict[str, Any]
    ) -> float:
        """
        Compute weighted overall confidence.
        
        Args:
            fields: Extracted fields
            field_defs: Field definitions with weights
            
        Returns:
            Overall confidence score (0-1)
        """
        if not fields:
            return 0.0
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for field_name, field in fields.items():
            if field_name in field_defs:
                weight = field_defs[field_name].weight
                total_weight += weight
                weighted_sum += field.confidence * weight
        
        if total_weight == 0:
            return 0.0
        
        return min(weighted_sum / total_weight, 0.99)  # Never 1.0
