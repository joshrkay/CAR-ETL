"""Pydantic models for RAG pipeline."""
from uuid import UUID

from pydantic import BaseModel, Field


class ChunkMatch(BaseModel):
    """Retrieved chunk with similarity score."""
    id: UUID = Field(..., description="Chunk UUID")
    document_id: UUID = Field(..., description="Document UUID")
    content: str = Field(..., description="Chunk content (redacted)")
    page_numbers: list[int] = Field(default_factory=list, description="Pages where chunk appears")
    similarity: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")
    section_header: str | None = Field(None, description="Section header if available")


class Citation(BaseModel):
    """Citation linking answer to source document."""
    document_id: UUID = Field(..., description="Source document UUID")
    document_name: str = Field(..., description="Source document filename")
    page: int = Field(..., ge=1, description="Page number")
    snippet: str = Field(..., description="Relevant text snippet from source")


class AskRequest(BaseModel):
    """Request to ask a question about documents."""
    question: str = Field(..., min_length=1, description="Question to answer")
    document_ids: list[UUID] | None = Field(
        None, description="Optional filter to specific documents"
    )
    max_chunks: int = Field(
        default=5, ge=1, le=20, description="Maximum chunks to use in context"
    )


class AskResponse(BaseModel):
    """Response to a document question."""
    answer: str = Field(..., description="Generated answer with citations")
    citations: list[Citation] = Field(
        default_factory=list, description="Citations backing the answer"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the answer"
    )
    chunks_used: int = Field(..., ge=0, description="Number of chunks used")
    suggestion: str | None = Field(
        None, description="Suggestion for improving query if no answer"
    )
