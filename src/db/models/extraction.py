"""Pydantic models for extraction results."""
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ExtractionStatus(str, Enum):
    """Extraction processing status."""
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionSource(str, Enum):
    """Source of extraction field value."""
    PARSER = "parser"
    LLM = "llm"
    RULE = "rule"


class DocumentType(str, Enum):
    """Document type classification."""
    LEASE = "lease"
    RENT_ROLL = "rent_roll"
    FINANCIAL_STATEMENT = "financial_statement"
    OPERATING_AGREEMENT = "operating_agreement"
    OTHER = "other"


class ParserType(str, Enum):
    """Parser used for extraction."""
    RAGFLOW = "ragflow"
    UNSTRUCTURED = "unstructured"
    TIKA = "tika"


class BoundingBox(BaseModel):
    """Bounding box coordinates as percentages."""
    x: float = Field(..., ge=0.0, le=100.0, description="X coordinate as percentage")
    y: float = Field(..., ge=0.0, le=100.0, description="Y coordinate as percentage")
    width: float = Field(..., ge=0.0, le=100.0, description="Width as percentage")
    height: float = Field(..., ge=0.0, le=100.0, description="Height as percentage")


class Extraction(BaseModel):
    """Extraction result model."""
    id: UUID = Field(..., description="Extraction UUID")
    tenant_id: UUID = Field(..., description="Tenant UUID")
    document_id: UUID = Field(..., description="Document UUID")
    version: int = Field(..., ge=1, description="Extraction version number")
    status: ExtractionStatus = Field(..., description="Extraction status")
    overall_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Overall confidence score"
    )
    document_type: DocumentType | None = Field(
        None, description="Document type classification"
    )
    parser_used: ParserType | None = Field(
        None, description="Parser used for extraction"
    )
    is_current: bool = Field(default=True, description="Whether this is the current extraction")
    error_message: str | None = Field(None, description="Error message if extraction failed")
    extracted_at: datetime | None = Field(None, description="When extraction completed")
    created_at: datetime = Field(..., description="When extraction was created")


class ExtractionField(BaseModel):
    """Extraction field model for key-value pairs."""
    id: UUID = Field(..., description="Field UUID")
    extraction_id: UUID = Field(..., description="Parent extraction UUID")
    field_name: str = Field(..., min_length=1, description="Field name/key")
    field_value: dict[str, Any] = Field(..., description="Field value as JSONB")
    raw_value: str | None = Field(None, description="Raw text value before processing")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    source: ExtractionSource = Field(..., description="Source of extraction")
    page_number: int | None = Field(None, ge=1, description="Page number where field was found")
    bounding_box: dict[str, Any] | None = Field(
        None, description="Bounding box coordinates as JSONB {x, y, width, height} as percentages"
    )
    is_override: bool = Field(default=False, description="Whether field was manually overridden")
    overridden_by: UUID | None = Field(None, description="User who overrode the field")
    overridden_at: datetime | None = Field(None, description="When field was overridden")
    created_at: datetime = Field(..., description="When field was created")


class ExtractionTable(BaseModel):
    """Extraction table model for tabular data."""
    id: UUID = Field(..., description="Table UUID")
    extraction_id: UUID = Field(..., description="Parent extraction UUID")
    table_name: str | None = Field(None, description="Table name/identifier")
    headers: list[str] = Field(..., description="Table column headers")
    rows: list[dict[str, Any]] = Field(..., description="Table rows as JSONB")
    page_number: int | None = Field(None, ge=1, description="Page number where table was found")
    confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Confidence score for table extraction"
    )
    created_at: datetime = Field(..., description="When table was created")


class ExtractionWithFields(BaseModel):
    """Extraction with associated fields."""
    extraction: Extraction = Field(..., description="Extraction record")
    fields: list[ExtractionField] = Field(default_factory=list, description="Extraction fields")
    tables: list[ExtractionTable] = Field(default_factory=list, description="Extraction tables")
