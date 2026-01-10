"""
Integration tests for RAG Q&A API endpoint.

Tests the complete flow from HTTP request to answer generation with citations.
"""

import pytest
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient

from src.main import app


class TestRAGIntegration:
    """Integration tests for RAG Q&A endpoint."""

    @pytest.fixture
    def mock_auth(self):
        """Mock authentication context."""
        return {
            "user_id": str(uuid4()),
            "tenant_id": str(uuid4()),
            "email": "test@example.com",
            "roles": ["User"],
        }

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_ask_endpoint_success(self, client, mock_auth):
        """Test successful question answering with citations."""
        doc_id = uuid4()
        chunk_id = uuid4()

        with patch("src.api.routes.ask.get_supabase_client") as mock_get_supabase:
            with patch("src.api.routes.ask.require_permission") as mock_auth_dep:
                with patch("src.rag.generator.AsyncOpenAI") as mock_openai:
                    # Mock auth
                    mock_auth_context = Mock()
                    mock_auth_context.user_id = uuid4()
                    mock_auth_context.tenant_id = uuid4()
                    mock_auth_dep.return_value = lambda: mock_auth_context

                    # Mock Supabase
                    mock_supabase = Mock()
                    mock_get_supabase.return_value = mock_supabase

                    # Mock RPC for vector search
                    mock_supabase.rpc.return_value.execute.return_value.data = [
                        {
                            "id": str(chunk_id),
                            "document_id": str(doc_id),
                            "content": "The monthly base rent is $10,000 payable on the first of each month.",
                            "page_numbers": [5],
                            "similarity": 0.92,
                            "section_header": "Rent and Payment Terms",
                        }
                    ]

                    # Mock document name query
                    mock_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
                        {
                            "id": str(doc_id),
                            "original_filename": "Commercial_Lease_2024.pdf",
                        }
                    ]

                    # Mock OpenAI embedding
                    mock_embedding_response = Mock()
                    mock_embedding_response.data = [Mock(embedding=[0.1] * 1536)]

                    # Mock OpenAI chat completion
                    mock_chat_response = Mock()
                    mock_chat_response.choices = [Mock()]
                    mock_chat_response.choices[0].message.content = (
                        f"The monthly base rent is $10,000 [DOC:{doc_id}:PAGE:5], "
                        "payable on the first of each month."
                    )
                    mock_chat_response.usage.total_tokens = 150

                    mock_client = AsyncMock()
                    mock_client.embeddings.create = AsyncMock(
                        return_value=mock_embedding_response
                    )
                    mock_client.chat.completions.create = AsyncMock(
                        return_value=mock_chat_response
                    )
                    mock_openai.return_value = mock_client

                    # Make request
                    response = client.post(
                        "/api/v1/ask",
                        json={
                            "question": "What is the monthly base rent?",
                            "max_chunks": 5,
                        },
                    )

                    # Verify response
                    assert response.status_code == 200
                    data = response.json()

                    assert "answer" in data
                    assert "$10,000" in data["answer"]
                    assert len(data["citations"]) == 1
                    assert data["citations"][0]["document_name"] == "Commercial_Lease_2024.pdf"
                    assert data["citations"][0]["page"] == 5
                    assert data["chunks_used"] == 1
                    assert data["confidence"] > 0

    def test_ask_endpoint_no_context(self, client, mock_auth):
        """Test endpoint when no relevant context found."""
        with patch("src.api.routes.ask.get_supabase_client") as mock_get_supabase:
            with patch("src.api.routes.ask.require_permission") as mock_auth_dep:
                # Mock auth
                mock_auth_context = Mock()
                mock_auth_context.user_id = uuid4()
                mock_auth_context.tenant_id = uuid4()
                mock_auth_dep.return_value = lambda: mock_auth_context

                # Mock Supabase - return no chunks
                mock_supabase = Mock()
                mock_get_supabase.return_value = mock_supabase
                mock_supabase.rpc.return_value.execute.return_value.data = []

                # Mock OpenAI embedding
                with patch("src.rag.generator.AsyncOpenAI") as mock_openai:
                    mock_embedding_response = Mock()
                    mock_embedding_response.data = [Mock(embedding=[0.1] * 1536)]

                    mock_client = AsyncMock()
                    mock_client.embeddings.create = AsyncMock(
                        return_value=mock_embedding_response
                    )
                    mock_openai.return_value = mock_client

                    # Make request
                    response = client.post(
                        "/api/v1/ask",
                        json={
                            "question": "What is the answer to unknown question?",
                            "max_chunks": 5,
                        },
                    )

                    # Verify response
                    assert response.status_code == 200
                    data = response.json()

                    assert "don't have enough information" in data["answer"]
                    assert len(data["citations"]) == 0
                    assert data["confidence"] == 0.0
                    assert data["chunks_used"] == 0
                    assert data["suggestion"] is not None

    def test_ask_endpoint_with_document_filter(self, client, mock_auth):
        """Test endpoint with document_ids filter."""
        doc_id1 = uuid4()
        chunk_id = uuid4()

        with patch("src.api.routes.ask.get_supabase_client") as mock_get_supabase:
            with patch("src.api.routes.ask.require_permission") as mock_auth_dep:
                with patch("src.rag.generator.AsyncOpenAI") as mock_openai:
                    # Mock auth
                    mock_auth_context = Mock()
                    mock_auth_context.user_id = uuid4()
                    mock_auth_context.tenant_id = uuid4()
                    mock_auth_dep.return_value = lambda: mock_auth_context

                    # Mock Supabase
                    mock_supabase = Mock()
                    mock_get_supabase.return_value = mock_supabase

                    # Mock RPC should receive document filter
                    mock_supabase.rpc.return_value.execute.return_value.data = [
                        {
                            "id": str(chunk_id),
                            "document_id": str(doc_id1),
                            "content": "Filtered content",
                            "page_numbers": [1],
                            "similarity": 0.90,
                            "section_header": None,
                        }
                    ]

                    # Mock document name query
                    mock_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
                        {
                            "id": str(doc_id1),
                            "original_filename": "Filtered_Doc.pdf",
                        }
                    ]

                    # Mock OpenAI
                    with patch("src.search.embeddings.AsyncOpenAI") as mock_embeddings_openai:
                        mock_embedding_response = Mock()
                        mock_embedding_response.data = [Mock(embedding=[0.1] * 1536)]

                        mock_chat_response = Mock()
                        mock_chat_response.choices = [Mock()]
                        mock_chat_response.choices[0].message.content = (
                            f"Filtered answer [DOC:{doc_id1}:PAGE:1]"
                        )
                        mock_chat_response.usage.total_tokens = 100

                        mock_client = AsyncMock()
                        mock_client.embeddings.create = AsyncMock(
                            return_value=mock_embedding_response
                        )
                        mock_client.chat.completions.create = AsyncMock(
                            return_value=mock_chat_response
                        )
                        mock_openai.return_value = mock_client
                        mock_embeddings_openai.return_value = mock_client

                        # Make request with document filter
                        response = client.post(
                            "/api/v1/ask",
                            json={
                                "question": "Test question",
                                "document_ids": [str(doc_id1)],
                                "max_chunks": 5,
                            },
                        )

                        # Verify response
                        assert response.status_code == 200
                        data = response.json()

                        assert "answer" in data
                        assert len(data["citations"]) == 1
                        assert data["citations"][0]["document_id"] == str(doc_id1)

    def test_ask_endpoint_validation_error(self, client):
        """Test endpoint with invalid request."""
        with patch("src.api.routes.ask.get_supabase_client"):
            with patch("src.api.routes.ask.require_permission"):
                # Request with missing question
                response = client.post(
                    "/api/v1/ask",
                    json={
                        "max_chunks": 5,
                    },
                )

                # Should return validation error
                assert response.status_code == 422  # Unprocessable Entity

    def test_ask_endpoint_max_chunks_validation(self, client):
        """Test endpoint validates max_chunks range."""
        with patch("src.api.routes.ask.get_supabase_client"):
            with patch("src.api.routes.ask.require_permission"):
                # Request with invalid max_chunks (exceeds limit)
                response = client.post(
                    "/api/v1/ask",
                    json={
                        "question": "Test?",
                        "max_chunks": 100,  # Exceeds limit of 20
                    },
                )

                # Should return validation error
                assert response.status_code == 422
