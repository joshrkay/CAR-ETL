"""
Tests for extraction pipeline orchestration.

Includes unit tests for all pipeline steps and integration tests
for the full workflow.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import UUID, uuid4
from datetime import datetime
from typing import Dict, Any

from src.extraction.pipeline import (
    get_document,
    download_document,
    parse_document_content,
    redact_pii,
    extract_cre_fields,
    save_extraction,
    update_document_status,
    process_document,
    DocumentNotFoundError,
    DocumentAccessError,
    ExtractionPipelineError,
)
from src.extraction.extractor import ExtractionResult, ExtractedField
from src.exceptions import ParserError


class TestGetDocument:
    """Tests for get_document function."""

    @pytest.mark.asyncio
    async def test_get_document_success(self):
        """Test successful document retrieval."""
        document_id = uuid4()
        mock_document = {
            "id": str(document_id),
            "tenant_id": str(uuid4()),
            "mime_type": "application/pdf",
            "storage_path": "test/path.pdf",
            "status": "pending",
        }

        mock_supabase = Mock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[mock_document]
        )

        result = await get_document(mock_supabase, document_id)

        assert result == mock_document
        mock_supabase.table.assert_called_once_with("documents")

    @pytest.mark.asyncio
    async def test_get_document_not_found(self):
        """Test document not found error."""
        document_id = uuid4()

        mock_supabase = Mock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = Mock(
            data=[]
        )

        with pytest.raises(DocumentNotFoundError, match="Document not found"):
            await get_document(mock_supabase, document_id)

    @pytest.mark.asyncio
    async def test_get_document_database_error(self):
        """Test database error handling."""
        document_id = uuid4()

        mock_supabase = Mock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception(
            "Database error"
        )

        with pytest.raises(ExtractionPipelineError, match="Failed to retrieve document"):
            await get_document(mock_supabase, document_id)


class TestDownloadDocument:
    """Tests for download_document function."""

    @pytest.mark.asyncio
    async def test_download_document_success(self):
        """Test successful document download."""
        tenant_id = uuid4()
        storage_path = "uploads/test.pdf"
        content = b"PDF content here"

        mock_supabase = Mock()
        mock_supabase.storage.from_.return_value.download.return_value = content

        result = await download_document(mock_supabase, storage_path, tenant_id)

        assert result == content
        mock_supabase.storage.from_.assert_called_once_with(f"documents-{tenant_id}")
        mock_supabase.storage.from_.return_value.download.assert_called_once_with(storage_path)

    @pytest.mark.asyncio
    async def test_download_document_not_found(self):
        """Test document not found in storage."""
        tenant_id = uuid4()
        storage_path = "uploads/missing.pdf"

        mock_supabase = Mock()
        mock_supabase.storage.from_.return_value.download.return_value = None

        with pytest.raises(DocumentAccessError, match="Failed to download document"):
            await download_document(mock_supabase, storage_path, tenant_id)

    @pytest.mark.asyncio
    async def test_download_document_storage_error(self):
        """Test storage error handling."""
        tenant_id = uuid4()
        storage_path = "uploads/test.pdf"

        mock_supabase = Mock()
        mock_supabase.storage.from_.return_value.download.side_effect = Exception("Storage error")

        with pytest.raises(DocumentAccessError, match="Failed to download document"):
            await download_document(mock_supabase, storage_path, tenant_id)


class TestParseDocumentContent:
    """Tests for parse_document_content function."""

    @pytest.mark.asyncio
    async def test_parse_document_success(self):
        """Test successful document parsing."""
        content = b"PDF content"
        mime_type = "application/pdf"

        mock_parse_result = Mock()
        mock_parse_result.text = "Extracted text content"
        mock_parse_result.pages = [{"page": 1, "text": "Page 1"}]
        mock_parse_result.tables = []
        mock_parse_result.metadata = {"parser": "ragflow"}

        with patch("src.extraction.pipeline.route_document", new_callable=AsyncMock) as mock_route:
            mock_route.return_value = mock_parse_result

            result = await parse_document_content(content, mime_type)

            assert result["text"] == "Extracted text content"
            assert len(result["pages"]) == 1
            assert result["metadata"]["parser"] == "ragflow"
            mock_route.assert_called_once_with(content, mime_type)

    @pytest.mark.asyncio
    async def test_parse_document_parser_error(self):
        """Test parser error handling."""
        content = b"Invalid content"
        mime_type = "application/pdf"

        with patch("src.extraction.pipeline.route_document", new_callable=AsyncMock) as mock_route:
            mock_route.side_effect = Exception("Parser failed")

            with pytest.raises(ParserError, match="Failed to parse document"):
                await parse_document_content(content, mime_type)


class TestRedactPII:
    """Tests for redact_pii function."""

    @pytest.mark.asyncio
    async def test_redact_pii_enabled(self):
        """Test PII redaction when enabled."""
        text = "John Smith lives at 123 Main St"

        with patch("src.extraction.pipeline.presidio_redact") as mock_redact:
            mock_redact.return_value = "<PERSON> lives at <ADDRESS>"

            result = await redact_pii(text, enabled=True)

            assert result == "<PERSON> lives at <ADDRESS>"
            mock_redact.assert_called_once_with(text)

    @pytest.mark.asyncio
    async def test_redact_pii_disabled(self):
        """Test PII redaction when disabled."""
        text = "John Smith lives at 123 Main St"

        result = await redact_pii(text, enabled=False)

        assert result == text

    @pytest.mark.asyncio
    async def test_redact_pii_error(self):
        """Test PII redaction error handling."""
        text = "Some text"

        with patch("src.extraction.pipeline.presidio_redact") as mock_redact:
            mock_redact.side_effect = RuntimeError("Redaction failed")

            with pytest.raises(RuntimeError, match="Redaction failed"):
                await redact_pii(text, enabled=True)


class TestExtractCREFields:
    """Tests for extract_cre_fields function."""

    @pytest.mark.asyncio
    async def test_extract_cre_fields_with_document_type(self):
        """Test field extraction with provided document type."""
        document_text = "Lease agreement for ABC Corp..."
        document_type = "lease"

        mock_extraction_result = ExtractionResult(
            fields={
                "tenant_name": ExtractedField(
                    value="ABC Corp",
                    confidence=0.95,
                    page=1,
                    quote="ABC Corp",
                )
            },
            document_type="lease",
            overall_confidence=0.95,
        )

        with patch("src.extraction.pipeline.FieldExtractor") as mock_extractor_class:
            mock_extractor = Mock()
            mock_extractor.extract_fields = AsyncMock(return_value=mock_extraction_result)
            mock_extractor_class.return_value = mock_extractor

            result = await extract_cre_fields(document_text, document_type)

            assert result.document_type == "lease"
            assert result.overall_confidence == 0.95
            assert "tenant_name" in result.fields
            mock_extractor.extract_fields.assert_called_once_with(
                document_text,
                industry="cre",
                document_type="lease",
            )

    @pytest.mark.asyncio
    async def test_extract_cre_fields_auto_detect_type(self):
        """Test field extraction with auto-detection of document type."""
        document_text = "Lease agreement for ABC Corp..."

        mock_detection = {
            "document_type": "lease",
            "confidence": 0.92,
            "reasoning": "Contains lease language",
        }

        mock_extraction_result = ExtractionResult(
            fields={},
            document_type="lease",
            overall_confidence=0.85,
        )

        with patch("src.extraction.pipeline.FieldExtractor") as mock_extractor_class:
            mock_extractor = Mock()
            mock_extractor.detect_document_type = AsyncMock(return_value=mock_detection)
            mock_extractor.extract_fields = AsyncMock(return_value=mock_extraction_result)
            mock_extractor_class.return_value = mock_extractor

            result = await extract_cre_fields(document_text)

            assert result.document_type == "lease"
            mock_extractor.detect_document_type.assert_called_once()
            mock_extractor.extract_fields.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_cre_fields_error(self):
        """Test field extraction error handling."""
        document_text = "Some text"

        with patch("src.extraction.pipeline.FieldExtractor") as mock_extractor_class:
            mock_extractor = Mock()
            mock_extractor.detect_document_type = AsyncMock(
                side_effect=Exception("Extraction failed")
            )
            mock_extractor_class.return_value = mock_extractor

            with pytest.raises(Exception, match="Extraction failed"):
                await extract_cre_fields(document_text)


class TestSaveExtraction:
    """Tests for save_extraction function."""

    @pytest.mark.asyncio
    async def test_save_extraction_success(self):
        """Test successful extraction save."""
        document_id = uuid4()
        tenant_id = uuid4()
        extraction_id = uuid4()

        extraction_result = ExtractionResult(
            fields={
                "tenant_name": ExtractedField(
                    value="ABC Corp",
                    confidence=0.95,
                    page=1,
                    quote="ABC Corp",
                ),
                "base_rent": ExtractedField(
                    value=5000.00,
                    confidence=0.88,
                    page=2,
                    quote="$5,000",
                ),
            },
            document_type="lease",
            overall_confidence=0.91,
        )

        mock_supabase = Mock()

        # Mock extraction insert
        mock_supabase.table.return_value.insert.return_value.execute.return_value = Mock(
            data=[{"id": str(extraction_id)}]
        )

        result = await save_extraction(
            mock_supabase,
            document_id,
            tenant_id,
            extraction_result,
            parser_used="ragflow",
        )

        assert result == extraction_id

        # Verify extraction table insert was called
        calls = mock_supabase.table.call_args_list
        assert any("extractions" in str(call) for call in calls)
        assert any("extraction_fields" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_save_extraction_no_extraction_record(self):
        """Test save extraction when record creation fails."""
        document_id = uuid4()
        tenant_id = uuid4()

        extraction_result = ExtractionResult(
            fields={},
            document_type="lease",
            overall_confidence=0.5,
        )

        mock_supabase = Mock()
        mock_supabase.table.return_value.insert.return_value.execute.return_value = Mock(
            data=None
        )

        with pytest.raises(ExtractionPipelineError, match="Failed to create extraction record"):
            await save_extraction(
                mock_supabase,
                document_id,
                tenant_id,
                extraction_result,
                parser_used="tika",
            )

    @pytest.mark.asyncio
    async def test_save_extraction_database_error(self):
        """Test save extraction with database error."""
        document_id = uuid4()
        tenant_id = uuid4()

        extraction_result = ExtractionResult(
            fields={},
            document_type="lease",
            overall_confidence=0.5,
        )

        mock_supabase = Mock()
        mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception(
            "Database error"
        )

        with pytest.raises(ExtractionPipelineError, match="Failed to save extraction"):
            await save_extraction(
                mock_supabase,
                document_id,
                tenant_id,
                extraction_result,
                parser_used="tika",
            )


class TestUpdateDocumentStatus:
    """Tests for update_document_status function."""

    @pytest.mark.asyncio
    async def test_update_document_status_success(self):
        """Test successful status update."""
        document_id = uuid4()

        mock_supabase = Mock()

        await update_document_status(mock_supabase, document_id, "ready")

        mock_supabase.table.assert_called_once_with("documents")

    @pytest.mark.asyncio
    async def test_update_document_status_with_error(self):
        """Test status update with error message."""
        document_id = uuid4()
        error_message = "Parser failed"

        mock_supabase = Mock()

        await update_document_status(
            mock_supabase,
            document_id,
            "failed",
            error_message=error_message,
        )

        # Verify update was called with error_message
        mock_supabase.table.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_document_status_database_error(self):
        """Test status update with database error."""
        document_id = uuid4()

        mock_supabase = Mock()
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception(
            "Database error"
        )

        with pytest.raises(ExtractionPipelineError, match="Failed to update document status"):
            await update_document_status(mock_supabase, document_id, "ready")


class TestProcessDocument:
    """Integration tests for process_document function."""

    @pytest.mark.asyncio
    async def test_process_document_success(self):
        """Test successful end-to-end document processing."""
        document_id = uuid4()
        tenant_id = uuid4()
        extraction_id = uuid4()

        mock_document = {
            "id": str(document_id),
            "tenant_id": str(tenant_id),
            "mime_type": "application/pdf",
            "storage_path": "uploads/test.pdf",
            "status": "pending",
        }

        mock_content = b"PDF content"

        mock_parse_result = {
            "text": "Lease agreement text",
            "pages": [{"page": 1}],
            "tables": [],
            "metadata": {"parser": "ragflow"},
        }

        mock_extraction = ExtractionResult(
            fields={
                "tenant_name": ExtractedField(
                    value="ABC Corp",
                    confidence=0.95,
                    page=1,
                    quote="ABC Corp",
                )
            },
            document_type="lease",
            overall_confidence=0.95,
        )

        mock_supabase = Mock()

        # Mock all the database calls
        with patch("src.extraction.pipeline.get_document", new_callable=AsyncMock) as mock_get_doc, \
             patch("src.extraction.pipeline.download_document", new_callable=AsyncMock) as mock_download, \
             patch("src.extraction.pipeline.parse_document_content", new_callable=AsyncMock) as mock_parse, \
             patch("src.extraction.pipeline.redact_pii", new_callable=AsyncMock) as mock_redact, \
             patch("src.extraction.pipeline.extract_cre_fields", new_callable=AsyncMock) as mock_extract, \
             patch("src.extraction.pipeline.save_extraction", new_callable=AsyncMock) as mock_save, \
             patch("src.extraction.pipeline.update_document_status", new_callable=AsyncMock) as mock_update:

            mock_get_doc.return_value = mock_document
            mock_download.return_value = mock_content
            mock_parse.return_value = mock_parse_result
            mock_redact.return_value = "Redacted text"
            mock_extract.return_value = mock_extraction
            mock_save.return_value = extraction_id

            result = await process_document(document_id, mock_supabase)

            assert result["status"] == "ready"
            assert result["extraction_id"] == str(extraction_id)
            assert result["overall_confidence"] == 0.95
            assert result["error"] is None

            # Verify all steps were called
            mock_get_doc.assert_called_once()
            mock_download.assert_called_once()
            mock_parse.assert_called_once()
            mock_redact.assert_called_once()
            mock_extract.assert_called_once()
            mock_save.assert_called_once()

            # Verify status updates
            assert mock_update.call_count == 2  # processing and ready

    @pytest.mark.asyncio
    async def test_process_document_parsing_failure(self):
        """Test document processing with parsing failure."""
        document_id = uuid4()
        tenant_id = uuid4()

        mock_document = {
            "id": str(document_id),
            "tenant_id": str(tenant_id),
            "mime_type": "application/pdf",
            "storage_path": "uploads/test.pdf",
            "status": "pending",
        }

        mock_supabase = Mock()

        with patch("src.extraction.pipeline.get_document", new_callable=AsyncMock) as mock_get_doc, \
             patch("src.extraction.pipeline.download_document", new_callable=AsyncMock) as mock_download, \
             patch("src.extraction.pipeline.parse_document_content", new_callable=AsyncMock) as mock_parse, \
             patch("src.extraction.pipeline.update_document_status", new_callable=AsyncMock) as mock_update:

            mock_get_doc.return_value = mock_document
            mock_download.return_value = b"content"
            mock_parse.side_effect = ParserError("Parser failed")

            result = await process_document(document_id, mock_supabase)

            assert result["status"] == "failed"
            assert result["error"] is not None
            assert "Parser failed" in result["error"]

            # Verify status was updated to failed
            mock_update.assert_called()

    @pytest.mark.asyncio
    async def test_process_document_extraction_failure(self):
        """Test document processing with extraction failure."""
        document_id = uuid4()
        tenant_id = uuid4()

        mock_document = {
            "id": str(document_id),
            "tenant_id": str(tenant_id),
            "mime_type": "application/pdf",
            "storage_path": "uploads/test.pdf",
            "status": "pending",
        }

        mock_parse_result = {
            "text": "Some text",
            "pages": [],
            "tables": [],
            "metadata": {},
        }

        mock_supabase = Mock()

        with patch("src.extraction.pipeline.get_document", new_callable=AsyncMock) as mock_get_doc, \
             patch("src.extraction.pipeline.download_document", new_callable=AsyncMock) as mock_download, \
             patch("src.extraction.pipeline.parse_document_content", new_callable=AsyncMock) as mock_parse, \
             patch("src.extraction.pipeline.redact_pii", new_callable=AsyncMock) as mock_redact, \
             patch("src.extraction.pipeline.extract_cre_fields", new_callable=AsyncMock) as mock_extract, \
             patch("src.extraction.pipeline.update_document_status", new_callable=AsyncMock) as mock_update:

            mock_get_doc.return_value = mock_document
            mock_download.return_value = b"content"
            mock_parse.return_value = mock_parse_result
            mock_redact.return_value = "Redacted"
            mock_extract.side_effect = Exception("Extraction failed")

            result = await process_document(document_id, mock_supabase)

            assert result["status"] == "failed"
            assert "Extraction failed" in result["error"]

    @pytest.mark.asyncio
    async def test_process_document_not_found(self):
        """Test document processing with document not found."""
        document_id = uuid4()
        mock_supabase = Mock()

        with patch("src.extraction.pipeline.get_document", new_callable=AsyncMock) as mock_get_doc, \
             patch("src.extraction.pipeline.update_document_status", new_callable=AsyncMock) as mock_update:

            mock_get_doc.side_effect = DocumentNotFoundError("Document not found")

            result = await process_document(document_id, mock_supabase)

            assert result["status"] == "failed"
            assert "Document not found" in result["error"]


class TestPipelineEdgeCases:
    """Tests for edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_empty_extraction_fields(self):
        """Test save extraction with no fields."""
        document_id = uuid4()
        tenant_id = uuid4()
        extraction_id = uuid4()

        extraction_result = ExtractionResult(
            fields={},
            document_type="other",
            overall_confidence=0.0,
        )

        mock_supabase = Mock()
        mock_supabase.table.return_value.insert.return_value.execute.return_value = Mock(
            data=[{"id": str(extraction_id)}]
        )

        result = await save_extraction(
            mock_supabase,
            document_id,
            tenant_id,
            extraction_result,
            parser_used="tika",
        )

        # Should still save extraction record even with no fields
        assert result == extraction_id

    @pytest.mark.asyncio
    async def test_redact_empty_text(self):
        """Test PII redaction with empty text."""
        result = await redact_pii("", enabled=True)
        assert result == ""

    @pytest.mark.asyncio
    async def test_parse_document_empty_content(self):
        """Test parsing empty document."""
        content = b""
        mime_type = "application/pdf"

        with patch("src.extraction.pipeline.route_document", new_callable=AsyncMock) as mock_route:
            mock_route.side_effect = ParserError("Empty content")

            with pytest.raises(ParserError):
                await parse_document_content(content, mime_type)
