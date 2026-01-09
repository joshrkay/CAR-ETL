"""Pydantic models for extraction results."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from enum import Enum


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
    overall_confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Overall confidence score"
    )
    document_type: Optional[DocumentType] = Field(
        None, description="Document type classification"
    )
    parser_used: Optional[ParserType] = Field(
        None, description="Parser used for extraction"
    )
    is_current: bool = Field(default=True, description="Whether this is the current extraction")
    error_message: Optional[str] = Field(None, description="Error message if extraction failed")
    extracted_at: Optional[datetime] = Field(None, description="When extraction completed")
    created_at: datetime = Field(..., description="When extraction was created")


class ExtractionField(BaseModel):
    """Extraction field model for key-value pairs."""
    id: UUID = Field(..., description="Field UUID")
    extraction_id: UUID = Field(..., description="Parent extraction UUID")
    field_name: str = Field(..., min_length=1, description="Field name/key")
    field_value: Dict[str, Any] = Field(..., description="Field value as JSONB")
    raw_value: Optional[str] = Field(None, description="Raw text value before processing")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    source: ExtractionSource = Field(..., description="Source of extraction")
    page_number: Optional[int] = Field(None, ge=1, description="Page number where field was found")
    bounding_box: Optional[Dict[str, Any]] = Field(
        None, description="Bounding box coordinates as JSONB {x, y, width, height} as percentages"
    )
    is_override: bool = Field(default=False, description="Whether field was manually overridden")
    overridden_by: Optional[UUID] = Field(None, description="User who overrode the field")
    overridden_at: Optional[datetime] = Field(None, description="When field was overridden")
    created_at: datetime = Field(..., description="When field was created")


class ExtractionTable(BaseModel):
    """Extraction table model for tabular data."""
    id: UUID = Field(..., description="Table UUID")
    extraction_id: UUID = Field(..., description="Parent extraction UUID")
    table_name: Optional[str] = Field(None, description="Table name/identifier")
    headers: List[str] = Field(..., description="Table column headers")
    rows: List[Dict[str, Any]] = Field(..., description="Table rows as JSONB")
    page_number: Optional[int] = Field(None, ge=1, description="Page number where table was found")
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Confidence score for table extraction"
    )
    created_at: datetime = Field(..., description="When table was created")


class ExtractionWithFields(BaseModel):
    """Extraction with associated fields."""
    extraction: Extraction = Field(..., description="Extraction record")
    fields: List[ExtractionField] = Field(default_factory=list, description="Extraction fields")
    tables: List[ExtractionTable] = Field(default_factory=list, description="Extraction tables")
