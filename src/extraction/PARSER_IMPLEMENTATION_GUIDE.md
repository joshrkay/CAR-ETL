# Parser Implementation Guide

This guide outlines what's needed to implement the actual API integrations for each parser.

## Common Requirements

### 1. Dependencies
All parsers need `httpx` (already in `requirements.txt`). Additional dependencies:

```bash
# For spreadsheet parsers
pandas>=2.0.0
openpyxl>=3.1.0
```

### 2. Environment Variables
Add to `.env` file:

```bash
# RagFlow Configuration
RAGFLOW_API_URL=https://api.ragflow.example.com
RAGFLOW_API_KEY=your_api_key_here

# Unstructured.io Configuration
UNSTRUCTURED_API_URL=https://api.unstructured.io
UNSTRUCTURED_API_KEY=your_api_key_here

# Apache Tika Configuration
TIKA_API_URL=http://localhost:9998
# Tika typically doesn't require API key
```

### 3. Configuration Loading Pattern
Create a parser config similar to `src/auth/config.py`:

```python
# src/extraction/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class ParserConfig(BaseSettings):
    ragflow_api_url: str
    ragflow_api_key: str
    unstructured_api_url: str
    unstructured_api_key: str
    tika_api_url: str
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
```

---

## 1. RagFlow Parser

### API Documentation
- **Endpoint**: `POST /api/v1/parse` (example)
- **Authentication**: API key in header
- **Request**: Multipart form with file
- **Response**: JSON with text, pages, tables

### Implementation Steps

1. **Make API Request**:
```python
import httpx
import base64
from io import BytesIO

async def parse(self, content: bytes, mime_type: str) -> ParseResult:
    url = f"{self.api_url}/api/v1/parse"
    headers = {
        "Authorization": f"Bearer {self.api_key}",
    }
    
    files = {
        "file": (filename, content, mime_type)
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, files=files)
        response.raise_for_status()
        data = response.json()
```

2. **Parse Response**:
```python
    # Extract text
    text = data.get("text", "")
    
    # Extract pages
    pages = []
    for page_data in data.get("pages", []):
        pages.append(PageContent(
            page_number=page_data["page_number"],
            text=page_data["text"],
            metadata=page_data.get("metadata", {})
        ))
    
    # Extract tables
    tables = []
    for table_data in data.get("tables", []):
        tables.append(ExtractedTable(
            table_name=table_data.get("name"),
            headers=table_data["headers"],
            rows=table_data["rows"],
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
```

3. **Error Handling**:
```python
    except httpx.HTTPStatusError as e:
        raise ParserError("ragflow", f"HTTP {e.response.status_code}: {e.response.text}")
    except httpx.TimeoutException:
        raise ParserError("ragflow", "Request timeout")
    except Exception as e:
        raise ParserError("ragflow", f"Unexpected error: {str(e)}")
```

4. **Health Check**:
```python
async def health_check(self) -> bool:
    try:
        url = f"{self.api_url}/health"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            return response.status_code == 200
    except Exception:
        return False
```

---

## 2. Unstructured Parser

### API Documentation
- **Endpoint**: `POST /general/v0/general` (Unstructured.io API)
- **Authentication**: API key in header
- **Request**: Multipart form with file
- **Response**: JSON array of elements

### Implementation Steps

1. **Make API Request**:
```python
async def parse(self, content: bytes, mime_type: str) -> ParseResult:
    url = f"{self.api_url}/general/v0/general"
    headers = {
        "Authorization": f"Bearer {self.api_key}",
    }
    
    files = {
        "files": (filename, content, mime_type)
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, files=files)
        response.raise_for_status()
        elements = response.json()
```

2. **Parse Elements**:
```python
    # Unstructured returns array of elements
    text_parts = []
    pages = []
    tables = []
    current_page = 1
    
    for element in elements:
        element_type = element.get("type")
        
        if element_type == "NarrativeText" or element_type == "Title":
            text_parts.append(element.get("text", ""))
            # Track page numbers
            page_num = element.get("metadata", {}).get("page_number", current_page)
            current_page = page_num
        
        elif element_type == "Table":
            # Extract table structure
            table_html = element.get("metadata", {}).get("text_as_html", "")
            # Parse HTML table to get headers and rows
            headers, rows = self._parse_html_table(table_html)
            tables.append(ExtractedTable(
                headers=headers,
                rows=rows,
                page_number=element.get("metadata", {}).get("page_number")
            ))
    
    # Group text by pages
    # ... (implementation depends on Unstructured response structure)
    
    return ParseResult(
        text="\n\n".join(text_parts),
        pages=pages,
        tables=tables,
        metadata={"elements_count": len(elements)},
        parser_confidence=None
    )
```

---

## 3. Apache Tika Parser

### API Documentation
- **Endpoint**: `PUT /tika` (text extraction)
- **Endpoint**: `PUT /tika/form` (structured data)
- **Authentication**: None (typically)
- **Request**: Raw file bytes
- **Response**: Plain text or JSON

### Implementation Steps

1. **Make API Request**:
```python
async def parse(self, content: bytes, mime_type: str) -> ParseResult:
    # Tika text extraction
    url = f"{self.api_url}/tika"
    headers = {
        "Content-Type": mime_type,
        "Accept": "text/plain",
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.put(url, headers=headers, content=content)
        response.raise_for_status()
        text = response.text
```

2. **Extract Metadata** (optional):
```python
    # Get metadata separately
    metadata_url = f"{self.api_url}/meta"
    async with httpx.AsyncClient(timeout=30.0) as client:
        meta_response = await client.put(metadata_url, headers=headers, content=content)
        metadata = meta_response.json() if meta_response.headers.get("content-type") == "application/json" else {}
```

3. **Build ParseResult**:
```python
    # Tika doesn't provide page-by-page or table extraction by default
    # Split text by page breaks if available in metadata
    pages = []
    if "xmpTPg:NPages" in metadata:
        num_pages = int(metadata["xmpTPg:NPages"])
        # Simple split (may need more sophisticated logic)
        text_per_page = len(text) // num_pages if num_pages > 0 else [text]
        for i, page_text in enumerate(text_per_page, 1):
            pages.append(PageContent(
                page_number=i,
                text=page_text,
                metadata={}
            ))
    else:
        # Single page
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
```

---

## 4. Pandas Parser (Excel)

### Dependencies
```bash
pandas>=2.0.0
openpyxl>=3.1.0  # For .xlsx support
```

### Implementation Steps

1. **Read Excel File**:
```python
import pandas as pd
from io import BytesIO

async def parse(self, content: bytes, mime_type: str) -> ParseResult:
    excel_file = BytesIO(content)
    
    # Read all sheets
    excel_data = pd.read_excel(excel_file, sheet_name=None, engine='openpyxl')
    
    text_parts = []
    tables = []
    
    for sheet_name, df in excel_data.items():
        # Convert DataFrame to text representation
        text_parts.append(f"Sheet: {sheet_name}\n{df.to_string()}")
        
        # Extract as table
        headers = df.columns.tolist()
        rows = df.fillna("").to_dict('records')  # Replace NaN with empty strings
        
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
```

2. **Error Handling**:
```python
    except pd.errors.EmptyDataError:
        raise ParserError("pandas", "Excel file is empty")
    except pd.errors.ParserError as e:
        raise ParserError("pandas", f"Failed to parse Excel: {str(e)}")
    except Exception as e:
        raise ParserError("pandas", f"Unexpected error: {str(e)}")
```

---

## 5. OpenPyXL Parser (Excel Fallback)

### Dependencies
```bash
openpyxl>=3.1.0
```

### Implementation Steps

1. **Read Excel File**:
```python
from openpyxl import load_workbook
from io import BytesIO

async def parse(self, content: bytes, mime_type: str) -> ParseResult:
    excel_file = BytesIO(content)
    workbook = load_workbook(excel_file, data_only=True)
    
    text_parts = []
    tables = []
    
    for sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        
        # Extract all cell values
        rows_data = []
        for row in sheet.iter_rows(values_only=True):
            rows_data.append(list(row))
        
        if rows_data:
            # First row as headers
            headers = [str(cell) if cell is not None else "" for cell in rows_data[0]]
            # Remaining rows as data
            rows = []
            for row_data in rows_data[1:]:
                rows.append({headers[i]: str(cell) if cell is not None else "" 
                            for i, cell in enumerate(row_data)})
            
            # Build text representation
            text_parts.append(f"Sheet: {sheet_name}\n" + "\n".join(["\t".join(map(str, row)) for row in rows_data]))
            
            tables.append(ExtractedTable(
                table_name=sheet_name,
                headers=headers,
                rows=rows,
                page_number=None,
                confidence=1.0
            ))
    
    return ParseResult(
        text="\n\n".join(text_parts),
        pages=[],
        tables=tables,
        metadata={"sheet_count": len(workbook.sheetnames)},
        parser_confidence=1.0
    )
```

---

## Common Implementation Patterns

### 1. Update Router Configuration Loading

Update `src/extraction/router.py`:

```python
from src.extraction.config import get_parser_config

def get_parser(parser_name: str) -> BaseParser:
    config = get_parser_config()
    
    if parser_name == "ragflow":
        return RagFlowParser(api_url=config.ragflow_api_url, api_key=config.ragflow_api_key)
    elif parser_name == "unstructured":
        return UnstructuredParser(api_url=config.unstructured_api_url, api_key=config.unstructured_api_key)
    elif parser_name == "tika":
        return TikaParser(api_url=config.tika_api_url)
    # ... etc
```

### 2. Error Handling Best Practices

```python
try:
    # API call
    response = await client.post(...)
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    if e.response.status_code == 401:
        raise ParserError(parser_name, "Authentication failed")
    elif e.response.status_code == 429:
        raise ParserError(parser_name, "Rate limit exceeded")
    else:
        raise ParserError(parser_name, f"HTTP {e.response.status_code}")
except httpx.TimeoutException:
    raise ParserError(parser_name, "Request timeout")
except httpx.RequestError as e:
    raise ParserError(parser_name, f"Request failed: {str(e)}")
except Exception as e:
    logger.exception(f"Unexpected error in {parser_name} parser")
    raise ParserError(parser_name, f"Unexpected error: {str(e)}")
```

### 3. Timeout Configuration

```python
# For large files, use longer timeouts
TIMEOUT_LARGE_FILE = 300.0  # 5 minutes
TIMEOUT_NORMAL = 60.0  # 1 minute
TIMEOUT_HEALTH_CHECK = 5.0  # 5 seconds

async with httpx.AsyncClient(timeout=TIMEOUT_NORMAL) as client:
    # ...
```

### 4. File Size Limits

```python
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

if len(content) > MAX_FILE_SIZE:
    raise ParserError(parser_name, f"File too large: {len(content)} bytes")
```

---

## Testing Requirements

### Unit Tests
- Mock HTTP responses for each parser
- Test error handling (timeouts, 4xx, 5xx)
- Test ParseResult construction

### Integration Tests
- Test with real API endpoints (if available)
- Test with sample documents
- Test fallback behavior

### Property-Based Tests
- Test with various file sizes
- Test with corrupted files
- Test with edge cases (empty files, very large files)

---

## Security Considerations

1. **API Key Storage**: Never log API keys
2. **Content Validation**: Validate file content before sending to external APIs
3. **Rate Limiting**: Implement rate limiting for parser API calls
4. **Timeout Protection**: Always set timeouts to prevent hanging requests
5. **Error Messages**: Don't expose internal API errors to users

---

## Next Steps

1. Add parser dependencies to `requirements.txt`
2. Create `src/extraction/config.py` for configuration
3. Implement each parser following the patterns above
4. Add unit tests for each parser
5. Update router to load config from environment
6. Test with real documents
