"""
Apache Tika Parser - Understanding Plane

Parser implementation for Apache Tika service.
Fallback parser for various document formats.
"""
import logging
import httpx
from typing import Dict, Any, List
from .base import BaseParser, ParseResult, PageContent
from src.exceptions import ParserError

logger = logging.getLogger(__name__)

TIMEOUT_NORMAL = 60.0
TIMEOUT_HEALTH_CHECK = 5.0


class TikaParser(BaseParser):
    """Parser implementation using Apache Tika service."""
    
    def __init__(self, api_url: str):
        """
        Initialize Tika parser.
        
        Args:
            api_url: Tika API endpoint URL
        """
        self.api_url = api_url.rstrip("/")
    
    async def parse(self, content: bytes, mime_type: str) -> ParseResult:
        """
        Parse document using Apache Tika.
        
        Args:
            content: Raw document bytes
            mime_type: MIME type of the document
            
        Returns:
            ParseResult with extracted content
            
        Raises:
            ParserError: If parsing fails
        """
        if not self.api_url:
            raise ParserError("tika", "Tika API URL must be configured")
        
        # Extract text
        text_url = f"{self.api_url}/tika"
        text_headers = {
            "Content-Type": mime_type,
            "Accept": "text/plain",
        }
        
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_NORMAL) as client:
                text_response = await client.put(text_url, headers=text_headers, content=content)
                text_response.raise_for_status()
                text = text_response.text
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}"
            raise ParserError("tika", error_msg)
        except httpx.TimeoutException:
            raise ParserError("tika", "Request timeout")
        except httpx.RequestError as e:
            raise ParserError("tika", f"Request failed: {str(e)}")
        except Exception as e:
            logger.exception("Unexpected error in Tika parser")
            raise ParserError("tika", f"Unexpected error: {str(e)}")
        
        # Extract metadata
        metadata: Dict[str, Any] = {}
        try:
            metadata_url = f"{self.api_url}/meta"
            async with httpx.AsyncClient(timeout=30.0) as client:
                meta_response = await client.put(
                    metadata_url, 
                    headers=text_headers, 
                    content=content
                )
                if meta_response.headers.get("content-type", "").startswith("application/json"):
                    metadata = meta_response.json()
        except Exception:
            # Metadata extraction is optional, continue without it
            logger.debug("Failed to extract metadata from Tika")
        
        # Build pages
        pages: List[PageContent] = []
        num_pages = 1
        
        # Try to get page count from metadata
        if "xmpTPg:NPages" in metadata:
            try:
                num_pages = int(metadata["xmpTPg:NPages"])
            except (ValueError, TypeError):
                pass
        
        if num_pages > 1 and text:
            # Simple split by approximate page size
            text_length = len(text)
            chars_per_page = text_length // num_pages
            for i in range(num_pages):
                start = i * chars_per_page
                end = (i + 1) * chars_per_page if i < num_pages - 1 else text_length
                page_text = text[start:end].strip()
                if page_text:
                    pages.append(PageContent(
                        page_number=i + 1,
                        text=page_text,
                        metadata={}
                    ))
        else:
            # Single page
            if text.strip():
                pages.append(PageContent(
                    page_number=1,
                    text=text,
                    metadata={}
                ))
        
        return ParseResult(
            text=text,
            pages=pages,
            tables=[],  # Tika doesn't extract tables by default
            metadata=metadata,
            parser_confidence=None
        )
    
    async def health_check(self) -> bool:
        """
        Check if Tika service is available.
        
        Returns:
            True if service is healthy, False otherwise
        """
        if not self.api_url:
            return False
        
        try:
            url = f"{self.api_url}/tika"
            async with httpx.AsyncClient(timeout=TIMEOUT_HEALTH_CHECK) as client:
                response = await client.get(url)
                return bool(response.status_code == 200)
        except Exception:
            return False
