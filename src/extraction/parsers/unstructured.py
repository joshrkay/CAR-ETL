"""
Unstructured Parser - Understanding Plane

Parser implementation for Unstructured.io service.
Supports various document formats including Word and text files.
"""
import logging
import httpx
from typing import Dict, Any, List
from .base import BaseParser, ParseResult, PageContent, ExtractedTable
from src.exceptions import ParserError

logger = logging.getLogger(__name__)

TIMEOUT_NORMAL = 60.0
TIMEOUT_HEALTH_CHECK = 5.0


class UnstructuredParser(BaseParser):
    """Parser implementation using Unstructured.io service."""
    
    def __init__(self, api_url: str, api_key: str):
        """
        Initialize Unstructured parser.
        
        Args:
            api_url: Unstructured API endpoint URL
            api_key: API key for authentication
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
    
    def _parse_html_table(self, html_content: str) -> tuple[List[str], List[Dict[str, Any]]]:
        """
        Parse HTML table to extract headers and rows.
        
        Args:
            html_content: HTML table content
            
        Returns:
            Tuple of (headers, rows)
        """
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")
            table = soup.find("table")
            
            if not table:
                return [], []
            
            headers = []
            rows = []
            
            # Extract headers from thead or first row
            thead = table.find("thead")
            if thead:
                header_row = thead.find("tr")
                if header_row:
                    headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
            
            # Extract rows from tbody
            tbody = table.find("tbody")
            if tbody:
                for tr in tbody.find_all("tr"):
                    cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                    if cells:
                        if not headers:
                            headers = cells
                        else:
                            row_dict = {headers[i] if i < len(headers) else f"col_{i}": cell 
                                      for i, cell in enumerate(cells)}
                            rows.append(row_dict)
            
            return headers, rows
        except ImportError:
            logger.warning("BeautifulSoup not available, cannot parse HTML tables")
            return [], []
        except Exception as e:
            logger.warning(f"Failed to parse HTML table: {str(e)}")
            return [], []
    
    async def parse(self, content: bytes, mime_type: str) -> ParseResult:
        """
        Parse document using Unstructured.io.
        
        Args:
            content: Raw document bytes
            mime_type: MIME type of the document
            
        Returns:
            ParseResult with extracted content
            
        Raises:
            ParserError: If parsing fails
        """
        if not self.api_url or not self.api_key:
            raise ParserError("unstructured", "Unstructured API URL and key must be configured")
        
        url = f"{self.api_url}/general/v0/general"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        files = {
            "files": ("document", content, mime_type)
        }
        
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_NORMAL) as client:
                response = await client.post(url, headers=headers, files=files)
                response.raise_for_status()
                elements = response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}"
            if e.response.status_code == 401:
                error_msg = "Authentication failed"
            elif e.response.status_code == 429:
                error_msg = "Rate limit exceeded"
            raise ParserError("unstructured", error_msg)
        except httpx.TimeoutException:
            raise ParserError("unstructured", "Request timeout")
        except httpx.RequestError as e:
            raise ParserError("unstructured", f"Request failed: {str(e)}")
        except Exception as e:
            logger.exception("Unexpected error in Unstructured parser")
            raise ParserError("unstructured", f"Unexpected error: {str(e)}")
        
        # Process elements
        text_parts: List[str] = []
        pages_dict: Dict[int, List[str]] = {}
        tables: List[ExtractedTable] = []
        
        for element in elements:
            element_type = element.get("type", "")
            element_text = element.get("text", "")
            metadata = element.get("metadata", {})
            page_number = metadata.get("page_number", 1)
            
            if element_type in ["NarrativeText", "Title", "ListItem"]:
                text_parts.append(element_text)
                if page_number not in pages_dict:
                    pages_dict[page_number] = []
                pages_dict[page_number].append(element_text)
            
            elif element_type == "Table":
                table_html = metadata.get("text_as_html", "")
                headers, rows = self._parse_html_table(table_html)
                
                if headers:
                    tables.append(ExtractedTable(
                        table_name=None,
                        headers=headers,
                        rows=rows,
                        page_number=page_number,
                        confidence=None
                    ))
        
        # Build pages
        pages = [
            PageContent(
                page_number=page_num,
                text="\n".join(page_texts),
                metadata={}
            )
            for page_num, page_texts in sorted(pages_dict.items())
        ]
        
        # If no pages but has text, create single page
        if not pages and text_parts:
            pages.append(PageContent(
                page_number=1,
                text="\n\n".join(text_parts),
                metadata={}
            ))
        
        return ParseResult(
            text="\n\n".join(text_parts),
            pages=pages,
            tables=tables,
            metadata={"elements_count": len(elements)},
            parser_confidence=None
        )
    
    async def health_check(self) -> bool:
        """
        Check if Unstructured service is available.
        
        Returns:
            True if service is healthy, False otherwise
        """
        if not self.api_url:
            return False
        
        try:
            url = f"{self.api_url}/healthcheck"
            async with httpx.AsyncClient(timeout=TIMEOUT_HEALTH_CHECK) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception:
            return False
