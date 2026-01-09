"""
Base Parser Interface - Understanding Plane

Defines the contract for all document parsers.
Each parser must implement parse() and health_check() methods.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class PageContent(BaseModel):
    """Content extracted from a single page."""
    page_number: int = Field(..., ge=1, description="Page number (1-indexed)")
    text: str = Field(..., description="Extracted text content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Page metadata")


class ExtractedTable(BaseModel):
    """Table extracted from document."""
    table_name: Optional[str] = Field(None, description="Table name/identifier")
    headers: list[str] = Field(..., description="Column headers")
    rows: list[Dict[str, Any]] = Field(..., description="Table rows")
    page_number: Optional[int] = Field(None, ge=1, description="Page number where table was found")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Extraction confidence")


class ParseResult(BaseModel):
    """Result of document parsing operation."""
    text: str = Field(..., description="Full extracted text")
    pages: list[PageContent] = Field(default_factory=list, description="Page-by-page content")
    tables: list[ExtractedTable] = Field(default_factory=list, description="Extracted tables")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Parser metadata")
    parser_confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Overall parser confidence score"
    )


class BaseParser(ABC):
    """Abstract base class for all document parsers."""
    
    @abstractmethod
    async def parse(self, content: bytes, mime_type: str) -> ParseResult:
        """
        Parse document content and extract text, pages, and tables.
        
        Args:
            content: Raw document bytes
            mime_type: MIME type of the document
            
        Returns:
            ParseResult with extracted content
            
        Raises:
            ParserError: If parsing fails
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if parser service is available and healthy.
        
        Returns:
            True if parser is healthy, False otherwise
        """
        pass
