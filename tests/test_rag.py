"""Tests for RAG Q&A pipeline."""
import pytest
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch

from src.rag.models import ChunkMatch, AskRequest, AskResponse
from src.rag.citations import extract_citations, validate_citations, build_citations
from src.rag.context_builder import count_tokens, build_context
from src.rag.prompts import format_system_prompt, format_user_prompt
from src.rag.retriever import Retriever
from src.rag.generator import Generator
from src.rag.pipeline import RAGPipeline


# ========== Citation Tests ==========

def test_extract_citations_valid() -> None:
    """Test extraction of valid citations from answer."""
    doc_id = str(uuid4())
    answer = f"The rent is $5000 [DOC:{doc_id}:PAGE:3] and deposit is $1000 [DOC:{doc_id}:PAGE:4]."

    citations = extract_citations(answer)

    assert len(citations) == 2
    assert (doc_id, 3) in citations
    assert (doc_id, 4) in citations


def test_extract_citations_no_citations() -> None:
    """Test extraction when no citations present."""
    answer = "I don't have enough information to answer this."

    citations = extract_citations(answer)

    assert citations == []


def test_validate_citations_valid() -> None:
    """Test validation with valid citations."""
    doc_id = uuid4()
    answer = f"The rent is $5000 [DOC:{doc_id}:PAGE:3]."

    chunks = [
        ChunkMatch(
            id=uuid4(),
            document_id=doc_id,
            content="Monthly rent: $5000",
            page_numbers=[3],
            similarity=0.95,
        )
    ]

    assert validate_citations(answer, chunks) is True


def test_validate_citations_invalid_doc() -> None:
    """Test validation fails when citation references unknown document."""
    doc_id1 = uuid4()
    doc_id2 = uuid4()
    answer = f"The rent is $5000 [DOC:{doc_id2}:PAGE:3]."

    chunks = [
        ChunkMatch(
            id=uuid4(),
            document_id=doc_id1,
            content="Monthly rent: $5000",
            page_numbers=[3],
            similarity=0.95,
        )
    ]

    assert validate_citations(answer, chunks) is False


def test_validate_citations_no_info_response() -> None:
    """Test validation passes for 'no information' responses."""
    answer = "I don't have enough information to answer this based on the available documents."
    chunks = []

    assert validate_citations(answer, chunks) is True


def test_build_citations() -> None:
    """Test building citation objects from answer and chunks."""
    doc_id = uuid4()
    answer = f"The rent is $5000 [DOC:{doc_id}:PAGE:3]."

    chunks = [
        ChunkMatch(
            id=uuid4(),
            document_id=doc_id,
            content="Monthly rent shall be five thousand dollars ($5000) payable on the first of each month.",
            page_numbers=[3],
            similarity=0.95,
        )
    ]

    document_names = {doc_id: "Lease Agreement.pdf"}

    citations = build_citations(answer, chunks, document_names)

    assert len(citations) == 1
    assert citations[0].document_id == doc_id
    assert citations[0].document_name == "Lease Agreement.pdf"
    assert citations[0].page == 3
    assert "Monthly rent" in citations[0].snippet


def test_build_citations_deduplicates() -> None:
    """Test that duplicate citations are removed."""
    doc_id = uuid4()
    answer = f"Rent is $5000 [DOC:{doc_id}:PAGE:3]. The amount is $5000 [DOC:{doc_id}:PAGE:3]."

    chunks = [
        ChunkMatch(
            id=uuid4(),
            document_id=doc_id,
            content="Monthly rent: $5000",
            page_numbers=[3],
            similarity=0.95,
        )
    ]

    document_names = {doc_id: "Lease.pdf"}

    citations = build_citations(answer, chunks, document_names)

    assert len(citations) == 1


# ========== Context Builder Tests ==========

def test_count_tokens() -> None:
    """Test token counting."""
    text = "This is a test sentence."
    tokens = count_tokens(text)

    assert isinstance(tokens, int)
    assert tokens > 0
    assert tokens < 100  # Short sentence should have few tokens


def test_build_context_single_chunk() -> None:
    """Test context building with single chunk."""
    doc_id = uuid4()
    chunks = [
        ChunkMatch(
            id=uuid4(),
            document_id=doc_id,
            content="This is chunk content.",
            page_numbers=[1],
            similarity=0.95,
        )
    ]

    context = build_context(chunks, max_tokens=1000)

    assert f"[DOC:{doc_id}:PAGE:1]" in context
    assert "This is chunk content." in context


def test_build_context_respects_token_limit() -> None:
    """Test that context builder respects token limit."""
    chunks = [
        ChunkMatch(
            id=uuid4(),
            document_id=uuid4(),
            content="A" * 1000,  # Long content
            page_numbers=[i],
            similarity=0.9,
        )
        for i in range(1, 100)
    ]

    context = build_context(chunks, max_tokens=100)

    # Should stop before using all chunks
    tokens = count_tokens(context)
    assert tokens <= 100


def test_build_context_multiple_chunks() -> None:
    """Test context building with multiple chunks."""
    chunks = [
        ChunkMatch(
            id=uuid4(),
            document_id=uuid4(),
            content=f"Chunk {i} content",
            page_numbers=[i],
            similarity=0.9 - i * 0.1,
        )
        for i in range(1, 4)
    ]

    context = build_context(chunks, max_tokens=6000)

    # All chunks should be included
    assert "Chunk 1 content" in context
    assert "Chunk 2 content" in context
    assert "Chunk 3 content" in context
    assert context.count("---") == 2  # Separators between chunks


# ========== Prompt Tests ==========

def test_format_system_prompt() -> None:
    """Test system prompt formatting."""
    context = "Test context"
    prompt = format_system_prompt(context)

    assert "CRE document analyst" in prompt
    assert "Test context" in prompt
    assert "citation" in prompt.lower()
    assert "[DOC:uuid:PAGE:n]" in prompt


def test_format_user_prompt() -> None:
    """Test user prompt formatting."""
    question = "What is the base rent?"
    prompt = format_user_prompt(question)

    assert prompt == question


# ========== Retriever Tests ==========

@pytest.mark.asyncio
async def test_retriever_retrieve():
    """Test retriever retrieval flow."""
    # Mock dependencies
    mock_supabase = Mock()
    mock_embeddings = AsyncMock()
    mock_embeddings.embed_single = AsyncMock(return_value=[0.1] * 1536)

    doc_id = uuid4()
    chunk_id = uuid4()

    mock_supabase.rpc.return_value.execute.return_value.data = [
        {
            "id": str(chunk_id),
            "document_id": str(doc_id),
            "content": "Test content",
            "page_numbers": [1],
            "similarity": 0.95,
            "section_header": None,
        }
    ]

    retriever = Retriever(mock_supabase, mock_embeddings)

    # Execute
    chunks = await retriever.retrieve("test question", top_k=20, rerank_to=5)

    # Verify
    assert len(chunks) == 1
    assert chunks[0].document_id == doc_id
    assert chunks[0].content == "Test content"
    assert chunks[0].similarity == 0.95

    mock_embeddings.embed_single.assert_called_once_with("test question")
    mock_supabase.rpc.assert_called_once()


@pytest.mark.asyncio
async def test_retriever_rerank():
    """Test retriever re-ranking."""
    mock_supabase = Mock()
    mock_embeddings = AsyncMock()
    mock_embeddings.embed_single = AsyncMock(return_value=[0.1] * 1536)

    # Return 10 chunks with varying similarities
    mock_data = [
        {
            "id": str(uuid4()),
            "document_id": str(uuid4()),
            "content": f"Content {i}",
            "page_numbers": [i],
            "similarity": 0.5 + i * 0.01,  # Increasing similarities
            "section_header": None,
        }
        for i in range(10)
    ]

    mock_supabase.rpc.return_value.execute.return_value.data = mock_data

    retriever = Retriever(mock_supabase, mock_embeddings)

    # Execute with rerank_to=3
    chunks = await retriever.retrieve("test", top_k=20, rerank_to=3)

    # Should return top 3 by similarity
    assert len(chunks) == 3
    # Should be sorted by similarity descending
    assert chunks[0].similarity >= chunks[1].similarity >= chunks[2].similarity


# ========== Generator Tests ==========

@pytest.mark.asyncio
async def test_generator_generate():
    """Test generator answer generation."""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Test answer [DOC:abc:PAGE:1]"
    mock_response.usage.total_tokens = 100

    with patch("src.rag.generator.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai.return_value = mock_client

        generator = Generator(api_key="test-key")
        answer = await generator.generate("What is the rent?", "Context here")

        assert answer == "Test answer [DOC:abc:PAGE:1]"
        mock_client.chat.completions.create.assert_called_once()


# ========== Pipeline Integration Tests ==========

@pytest.mark.asyncio
async def test_pipeline_ask_success():
    """Test full RAG pipeline with successful answer."""
    # Mock Supabase
    mock_supabase = Mock()
    doc_id = uuid4()
    chunk_id = uuid4()

    # Mock RPC call for retrieval
    mock_supabase.rpc.return_value.execute.return_value.data = [
        {
            "id": str(chunk_id),
            "document_id": str(doc_id),
            "content": "Monthly rent is $5000",
            "page_numbers": [3],
            "similarity": 0.95,
            "section_header": None,
        }
    ]

    # Mock documents table query
    mock_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
        {
            "id": str(doc_id),
            "original_filename": "Lease.pdf",
        }
    ]

    # Mock embedding service
    mock_embeddings = AsyncMock()
    mock_embeddings.embed_single = AsyncMock(return_value=[0.1] * 1536)

    # Mock generator
    mock_generator = AsyncMock()
    mock_generator.generate = AsyncMock(
        return_value=f"The monthly rent is $5000 [DOC:{doc_id}:PAGE:3]."
    )

    # Create pipeline
    pipeline = RAGPipeline(mock_supabase, mock_embeddings, mock_generator)

    # Execute
    request = AskRequest(question="What is the rent?", max_chunks=5)
    response = await pipeline.ask(request)

    # Verify
    assert isinstance(response, AskResponse)
    assert "5000" in response.answer
    assert len(response.citations) == 1
    assert response.citations[0].document_id == doc_id
    assert response.citations[0].page == 3
    assert response.chunks_used == 1
    assert response.confidence > 0


@pytest.mark.asyncio
async def test_pipeline_ask_no_chunks():
    """Test pipeline when no relevant chunks found."""
    mock_supabase = Mock()
    mock_supabase.rpc.return_value.execute.return_value.data = []

    mock_embeddings = AsyncMock()
    mock_embeddings.embed_single = AsyncMock(return_value=[0.1] * 1536)

    mock_generator = AsyncMock()

    pipeline = RAGPipeline(mock_supabase, mock_embeddings, mock_generator)

    request = AskRequest(question="Unknown question", max_chunks=5)
    response = await pipeline.ask(request)

    # Should return no-context response
    assert "don't have enough information" in response.answer
    assert len(response.citations) == 0
    assert response.confidence == 0.0
    assert response.chunks_used == 0
    assert response.suggestion is not None


@pytest.mark.asyncio
async def test_pipeline_ask_invalid_citations():
    """Test pipeline when generated answer has invalid citations."""
    mock_supabase = Mock()
    doc_id = uuid4()
    chunk_id = uuid4()

    mock_supabase.rpc.return_value.execute.return_value.data = [
        {
            "id": str(chunk_id),
            "document_id": str(doc_id),
            "content": "Content",
            "page_numbers": [1],
            "similarity": 0.95,
            "section_header": None,
        }
    ]

    mock_embeddings = AsyncMock()
    mock_embeddings.embed_single = AsyncMock(return_value=[0.1] * 1536)

    # Generator returns answer with invalid citation
    mock_generator = AsyncMock()
    invalid_doc_id = uuid4()
    mock_generator.generate = AsyncMock(
        return_value=f"Invalid citation [DOC:{invalid_doc_id}:PAGE:99]."
    )

    pipeline = RAGPipeline(mock_supabase, mock_embeddings, mock_generator)

    request = AskRequest(question="Test?", max_chunks=5)
    response = await pipeline.ask(request)

    # Should return no-context response due to validation failure
    assert "don't have enough information" in response.answer
    assert response.confidence == 0.0
