"""RAG pipeline orchestration."""
import logging
from uuid import UUID

from src.search.embeddings import EmbeddingService
from supabase import Client

from .citations import build_citations, validate_citations
from .context_builder import build_context
from .generator import Generator
from .models import AskRequest, AskResponse, ChunkMatch
from .retriever import Retriever

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    RAG pipeline for Q&A with mandatory citations.

    Pipeline flow:
    1. Embed question
    2. Retrieve candidate chunks (up to a fixed maximum, e.g. 20)
    3. Re-rank and select top-N chunks based on request.max_chunks (configurable, typically 1–20)
    4. Build LLM context
    5. Generate answer with citations
    6. Validate citations
    7. Return response
    """

    def __init__(
        self,
        supabase_client: Client,
        embedding_service: EmbeddingService,
        generator: Generator,
    ):
        """
        Initialize RAG pipeline.

        Args:
            supabase_client: Supabase client with user JWT
            embedding_service: Service for generating embeddings
            generator: LLM generator for answers
        """
        self.client = supabase_client
        self.retriever = Retriever(supabase_client, embedding_service)
        self.generator = generator

    async def ask(self, request: AskRequest) -> AskResponse:
        """
        Answer question about documents.

        Args:
            request: Question request with optional filters

        Returns:
            Answer response with citations
        """
        logger.info(
            "Processing RAG query",
            extra={
                "question_length": len(request.question),
                "max_chunks": request.max_chunks,
                "document_filter": bool(request.document_ids),
            },
        )

        # 1-3. Retrieve and re-rank chunks
        chunks = await self.retriever.retrieve(
            question=request.question,
            top_k=20,
            rerank_to=request.max_chunks,
            document_ids=request.document_ids,
        )

        # Handle no relevant chunks found
        if not chunks:
            logger.info("No relevant chunks found for question")
            return self._no_context_response()

        # 4. Build context
        context = build_context(chunks, max_tokens=6000)

        # 5. Generate answer
        answer = await self.generator.generate(request.question, context)

        # 6. Validate citations
        if not validate_citations(answer, chunks):
            logger.warning("Generated answer failed citation validation")
            return self._no_context_response()

        # 7. Fetch document names and build citations
        document_names = await self._fetch_document_names(chunks)
        citations = build_citations(answer, chunks, document_names)

        # Calculate confidence from chunk similarities
        confidence = self._calculate_confidence(chunks)

        response = AskResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            chunks_used=len(chunks),
            suggestion=None,  # No suggestion needed for successful answers
        )

        logger.info(
            "RAG query completed",
            extra={
                "chunks_used": len(chunks),
                "citations_count": len(citations),
                "confidence": confidence,
            },
        )

        return response

    async def _fetch_document_names(self, chunks: list[ChunkMatch]) -> dict[UUID, str]:
        """
        Fetch document filenames for citation building.

        Args:
            chunks: Retrieved chunks

        Returns:
            Mapping of document_id to filename
        """
        doc_ids = list({chunk.document_id for chunk in chunks})

        result = self.client.table("documents").select("id, original_filename").in_(
            "id", [str(doc_id) for doc_id in doc_ids]
        ).execute()

        doc_names = {}
        for row in result.data:
            doc_names[UUID(row["id"])] = row["original_filename"]

        return doc_names

    def _calculate_confidence(self, chunks: list[ChunkMatch]) -> float:
        """
        Calculate confidence from chunk similarities.

        Args:
            chunks: Retrieved chunks

        Returns:
            Overall confidence score (0-1)
        """
        if not chunks:
            return 0.0

        # Use average of top chunk similarities
        similarities = [chunk.similarity for chunk in chunks]
        return sum(similarities) / len(similarities)

    def _no_context_response(self) -> AskResponse:
        """
        Generate response when no relevant context found.

        Returns:
            AskResponse indicating insufficient information
        """
        return AskResponse(
            answer="I don't have enough information to answer this question based on the available documents.",
            citations=[],
            confidence=0.0,
            chunks_used=0,
            suggestion="Try uploading the relevant document or rephrasing your question.",
        )
