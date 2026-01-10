"""
Search Reranker - Understanding Plane (Optional)

Uses cross-encoder models to rerank top search results.
Cross-encoders provide more accurate relevance scoring than bi-encoders
but are slower, so they're only used on top-k results.

OPTIONAL: This module requires sentence-transformers library.
If not installed, the service will gracefully degrade to no reranking.
"""

import logging
from typing import List, Optional

try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    CrossEncoder = None

from src.search.hybrid import SearchResult

logger = logging.getLogger(__name__)


class SearchReranker:
    """
    Service for reranking search results using cross-encoder models.

    Cross-encoders jointly encode query and document for more accurate scoring.
    This is slower than bi-encoders (embeddings) but much more accurate.

    OPTIONAL: Gracefully degrades if sentence-transformers not installed.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        top_k: int = 20,
    ):
        """
        Initialize reranker service.

        Args:
            model_name: Hugging Face cross-encoder model name
            top_k: Number of top results to rerank (default 20)
        """
        self.model_name = model_name
        self.top_k = top_k
        self.model: Optional[CrossEncoder] = None

        if not CROSS_ENCODER_AVAILABLE:
            logger.warning(
                "sentence-transformers not installed, reranking disabled",
                extra={"model_name": model_name},
            )
            return

        try:
            self.model = CrossEncoder(model_name)
            logger.info(
                "Cross-encoder model loaded successfully",
                extra={"model_name": model_name},
            )
        except Exception as e:
            logger.error(
                "Failed to load cross-encoder model",
                extra={
                    "model_name": model_name,
                    "error": str(e),
                },
            )
            self.model = None

    def rerank(
        self,
        query: str,
        results: List[SearchResult],
    ) -> List[SearchResult]:
        """
        Rerank search results using cross-encoder.

        Takes top-k results, scores them with cross-encoder, and returns
        reranked results. If cross-encoder unavailable, returns original results.

        Args:
            query: Search query text
            results: List of search results to rerank

        Returns:
            Reranked list of SearchResult objects
            Original results if reranking unavailable
        """
        # Return original results if reranking unavailable
        if self.model is None or not CROSS_ENCODER_AVAILABLE:
            return results

        # Only rerank top-k results (for performance)
        if len(results) <= 1:
            return results

        top_results = results[: self.top_k]
        remaining_results = results[self.top_k :]

        try:
            # Prepare query-document pairs for cross-encoder
            pairs = [(query, result.content) for result in top_results]

            # Get cross-encoder scores
            scores = self.model.predict(pairs)

            # Update result scores and sort
            reranked = []
            for result, score in zip(top_results, scores):
                reranked.append(
                    SearchResult(
                        chunk_id=result.chunk_id,
                        document_id=result.document_id,
                        content=result.content,
                        page_numbers=result.page_numbers,
                        score=float(score),
                        metadata=result.metadata,
                    )
                )

            # Sort by new scores
            reranked.sort(key=lambda x: x.score, reverse=True)

            # Append remaining results (not reranked)
            reranked.extend(remaining_results)

            logger.debug(
                "Reranked search results",
                extra={
                    "query_length": len(query),
                    "results_count": len(top_results),
                    "top_k": self.top_k,
                },
            )

            return reranked

        except Exception as e:
            logger.error(
                "Reranking failed, returning original results",
                extra={
                    "error": str(e),
                    "results_count": len(results),
                },
            )
            return results

    def is_available(self) -> bool:
        """
        Check if reranking is available.

        Returns:
            True if cross-encoder model loaded successfully
        """
        return self.model is not None
