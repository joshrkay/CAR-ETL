"""
Embedding Service - Understanding Plane

Provides text embeddings using OpenAI for semantic search.
Embeds text in batches for efficiency.
"""

import logging
import os
from typing import List
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# OpenAI API key from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_BATCH_SIZE = 100  # OpenAI allows up to 2048 inputs per request


class EmbeddingService:
    """
    Service for generating text embeddings using OpenAI.
    
    Uses text-embedding-3-small model (1536 dimensions).
    Automatically batches requests for efficiency.
    """
    
    def __init__(self, api_key: str | None = None, batch_size: int = DEFAULT_BATCH_SIZE):
        """
        Initialize embedding service.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            batch_size: Number of texts to embed per API call (default: 100)
        """
        api_key = api_key or OPENAI_API_KEY
        if not api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "text-embedding-3-small"
        self.batch_size = batch_size
        self.embedding_dimension = 1536
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        SECURITY: Content sent to OpenAI API should be redacted if it contains PII.
        Call presidio_redact() on texts before embedding if they contain sensitive data.
        
        Automatically batches requests to respect API limits.
        All texts must be non-empty strings.
        
        Args:
            texts: List of text strings to embed (should be redacted if containing PII)
            
        Returns:
            List of embedding vectors (each is a list of 1536 floats)
            
        Raises:
            ValueError: If texts list is empty or contains non-string values
            Exception: If OpenAI API call fails
        """
        if not texts:
            return []
        
        # Validate inputs
        if not all(isinstance(text, str) and text.strip() for text in texts):
            raise ValueError("All texts must be non-empty strings")
        
        # Batch texts for efficient API calls
        all_embeddings: List[List[float]] = []
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                logger.debug(
                    "Generated embeddings for batch",
                    extra={
                        "batch_size": len(batch),
                        "batch_index": i // self.batch_size,
                        "total_batches": (len(texts) + self.batch_size - 1) // self.batch_size,
                    },
                )
            except Exception as e:
                logger.error(
                    "Failed to generate embeddings",
                    extra={
                        "batch_index": i // self.batch_size,
                        "batch_size": len(batch),
                        "error": str(e),
                    },
                )
                raise
        
        logger.info(
            "Generated embeddings for all texts",
            extra={
                "total_texts": len(texts),
                "total_batches": (len(texts) + self.batch_size - 1) // self.batch_size,
            },
        )
        
        return all_embeddings
    
    async def embed_single(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Convenience method for single text embeddings.
        
        Args:
            text: Text string to embed
            
        Returns:
            Embedding vector (list of 1536 floats)
        """
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Text must be a non-empty string")
        
        embeddings = await self.embed([text])
        return embeddings[0]
