"""
RagFlow Parser - Understanding Plane

Parser implementation for RagFlow service.
Supports OCR for scanned documents and table extraction.
"""
import logging

import httpx

from src.exceptions import ParserError

from .base import BaseParser, ExtractedTable, PageContent, ParseResult

logger = logging.getLogger(__name__)

TIMEOUT_NORMAL = 60.0
TIMEOUT_HEALTH_CHECK = 5.0


class RagFlowParser(BaseParser):
    """Parser implementation using RagFlow service."""

    def __init__(self, api_url: str, api_key: str):
        """
        Initialize RagFlow parser.

        Args:
            api_url: RagFlow API endpoint URL
            api_key: API key for authentication
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    async def parse(self, content: bytes, mime_type: str) -> ParseResult:
        """
        Parse document using RagFlow.

        Args:
            content: Raw document bytes
            mime_type: MIME type of the document

        Returns:
            ParseResult with extracted content

        Raises:
            ParserError: If parsing fails
        """
        if not self.api_url or not self.api_key:
            raise ParserError("ragflow", "RagFlow API URL and key must be configured")

        url = f"{self.api_url}/api/v1/parse"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        files = {
            "file": ("document", content, mime_type)
        }

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_NORMAL) as client:
                response = await client.post(url, headers=headers, files=files)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}"
            if e.response.status_code == 401:
                error_msg = "Authentication failed"
            elif e.response.status_code == 429:
                error_msg = "Rate limit exceeded"
            raise ParserError("ragflow", error_msg)
        except httpx.TimeoutException:
            raise ParserError("ragflow", "Request timeout")
        except httpx.RequestError as e:
            raise ParserError("ragflow", f"Request failed: {str(e)}")
        except Exception as e:
            logger.exception("Unexpected error in RagFlow parser")
            raise ParserError("ragflow", f"Unexpected error: {str(e)}")

        # Extract text
        text = data.get("text", "")

        # Extract pages
        pages: list[PageContent] = []
        for page_data in data.get("pages", []):
            pages.append(PageContent(
                page_number=page_data.get("page_number", len(pages) + 1),
                text=page_data.get("text", ""),
                metadata=page_data.get("metadata", {})
            ))

        # If no pages but has text, create single page
        if not pages and text:
            pages.append(PageContent(
                page_number=1,
                text=text,
                metadata={}
            ))

        # Extract tables
        tables = []
        for table_data in data.get("tables", []):
            tables.append(ExtractedTable(
                table_name=table_data.get("name"),
                headers=table_data.get("headers", []),
                rows=table_data.get("rows", []),
                page_number=table_data.get("page_number"),
                confidence=table_data.get("confidence")
            ))

        return ParseResult(
            text=text,
            pages=pages,
            tables=tables,
            metadata=data.get("metadata", {}),
            parser_confidence=data.get("confidence")
        )

    async def health_check(self) -> bool:
        """
        Check if RagFlow service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        if not self.api_url:
            return False

        try:
            url = f"{self.api_url}/health"
            async with httpx.AsyncClient(timeout=TIMEOUT_HEALTH_CHECK) as client:
                response = await client.get(url)
                return bool(response.status_code == 200)
        except Exception:
            return False
