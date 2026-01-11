"""Retriever for RAG pipeline: embed, retrieve, re-rank."""
import logging
from typing import List, Optional
from uuid import UUID
from supabase import Client

from src.search.embeddings import EmbeddingService
from .models import ChunkMatch

logger = logging.getLogger(__name__)


class Retriever:
    """
    Retrieval service for RAG pipeline.

    Handles query embedding, vector search, and re-ranking.
    """

    def __init__(self, supabase_client: Client, embedding_service: EmbeddingService):
        """
        Initialize retriever.

        Args:
            supabase_client: Supabase client with user JWT
            embedding_service: Service for generating embeddings
        """
        self.client = supabase_client
        self.embeddings = embedding_service

    async def retrieve(
        self,
        question: str,
        top_k: int = 20,
        rerank_to: int = 5,
        document_ids: Optional[List[UUID]] = None,
    ) -> List[ChunkMatch]:
        """
        Retrieve and re-rank chunks for question.

        Pipeline:
        1. Embed question
        2. Retrieve top-k chunks via vector similarity
        3. Re-rank to top-n most relevant

        Args:
            question: User question
            top_k: Number of chunks to retrieve initially
            rerank_to: Number of chunks after re-ranking
            document_ids: Optional filter to specific documents

        Returns:
            List of re-ranked ChunkMatch objects
        """
        # 1. Embed question
        logger.info("Embedding question", extra={"question_length": len(question)})
        query_embedding = await self.embeddings.embed_single(question)

        # 2. Retrieve top-k chunks
        logger.info("Retrieving chunks", extra={"top_k": top_k, "document_filter": bool(document_ids)})
        chunks = await self._search_chunks(
            embedding=query_embedding,
            match_count=top_k,
            document_ids=document_ids,
        )

        if not chunks:
            logger.info("No chunks retrieved for question")
            return []

        # 3. Re-rank to top-n
        logger.info("Re-ranking chunks", extra={"initial_count": len(chunks), "rerank_to": rerank_to})
        reranked = self._rerank(chunks, rerank_to)

        logger.info("Retrieved and re-ranked chunks", extra={"final_count": len(reranked)})
        return reranked

    async def _search_chunks(
        self,
        embedding: List[float],
        match_count: int,
        document_ids: Optional[List[UUID]],
    ) -> List[ChunkMatch]:
        """
        Search chunks using vector similarity.

        Calls match_document_chunks PostgreSQL function.

        Args:
            embedding: Query embedding vector
            match_count: Number of chunks to return
            document_ids: Optional document filter

        Returns:
            List of ChunkMatch objects
        """
        params = {
            "query_embedding": embedding,
            "match_count": match_count,
        }

        if document_ids:
            params["filter_document_ids"] = [str(doc_id) for doc_id in document_ids]

        result = self.client.rpc("match_document_chunks", params).execute()

        if result.data is None or result.data == []:
            return []

        chunks = []
        for row in result.data:
            chunks.append(ChunkMatch(
                id=UUID(row["id"]),
                document_id=UUID(row["document_id"]),
                content=row["content"],
                page_numbers=row.get("page_numbers") or [],
                similarity=row["similarity"],
                section_header=row.get("section_header"),
            ))

        return chunks

    def _rerank(self, chunks: List[ChunkMatch], top_n: int) -> List[ChunkMatch]:
        """
        Re-rank chunks by similarity score.

        Simple re-ranking: sort by similarity and take top-n.
        Future enhancement: use cross-encoder for more sophisticated re-ranking.

        Args:
            chunks: Initial retrieved chunks
            top_n: Number of top chunks to return

        Returns:
            Top-n chunks sorted by relevance
        """
        # Sort by similarity descending
        sorted_chunks = sorted(chunks, key=lambda c: c.similarity, reverse=True)
        return sorted_chunks[:top_n]
