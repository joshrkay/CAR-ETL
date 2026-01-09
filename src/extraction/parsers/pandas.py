"""
Pandas Parser - Understanding Plane

Parser implementation for Excel spreadsheets using pandas.
Primary parser for .xlsx files.
"""
import logging
from io import BytesIO
from typing import Dict, Any
from .base import BaseParser, ParseResult, PageContent, ExtractedTable
from src.exceptions import ParserError

logger = logging.getLogger(__name__)


class PandasParser(BaseParser):
    """Parser implementation using pandas for Excel files."""
    
    def __init__(self):
        """Initialize Pandas parser."""
        pass
    
    async def parse(self, content: bytes, mime_type: str) -> ParseResult:
        """
        Parse Excel spreadsheet using pandas.
        
        Args:
            content: Raw document bytes
            mime_type: MIME type of the document
            
        Returns:
            ParseResult with extracted content
            
        Raises:
            ParserError: If parsing fails
        """
        try:
            import pandas as pd
        except ImportError:
            raise ParserError("pandas", "pandas library not installed")
        
        excel_file = BytesIO(content)
        
        try:
            # Read all sheets
            excel_data = pd.read_excel(excel_file, sheet_name=None, engine='openpyxl')
        except pd.errors.EmptyDataError:
            raise ParserError("pandas", "Excel file is empty")
        except pd.errors.ParserError as e:
            raise ParserError("pandas", f"Failed to parse Excel: {str(e)}")
        except Exception as e:
            logger.exception("Unexpected error in Pandas parser")
            raise ParserError("pandas", f"Unexpected error: {str(e)}")
        
        text_parts = []
        tables = []
        
        for sheet_name, df in excel_data.items():
            # Convert DataFrame to text representation
            text_parts.append(f"Sheet: {sheet_name}\n{df.to_string()}")
            
            # Extract as table
            headers = df.columns.tolist()
            # Replace NaN with empty strings and convert to dict records
            rows = df.fillna("").to_dict('records')
            
            tables.append(ExtractedTable(
                table_name=sheet_name,
                headers=headers,
                rows=rows,
                page_number=None,  # Excel doesn't have pages
                confidence=1.0
            ))
        
        return ParseResult(
            text="\n\n".join(text_parts),
            pages=[],  # Excel doesn't have pages
            tables=tables,
            metadata={"sheet_count": len(excel_data)},
            parser_confidence=1.0
        )
    
    async def health_check(self) -> bool:
        """
        Check if pandas is available.
        
        Returns:
            True if pandas is installed, False otherwise
        """
        try:
            import pandas  # noqa: F401
            return True
        except ImportError:
            return False
