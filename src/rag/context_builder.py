"""Context builder for RAG pipeline with token limits."""

import tiktoken

from .models import ChunkMatch


def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """
    Count tokens in text using tiktoken.

    Args:
        text: Text to count tokens for
        model: Model name for encoding

    Returns:
        Number of tokens
    """
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))


def build_context(chunks: list[ChunkMatch], max_tokens: int = 6000) -> str:
    """
    Build context string from chunks, respecting token limit.

    Args:
        chunks: Retrieved chunks sorted by relevance
        max_tokens: Maximum tokens allowed in context

    Returns:
        Formatted context string with citations
    """
    context_parts: list[str] = []
    current_tokens = 0

    for chunk in chunks:
        # Format chunk with citation tag
        pages_str = str(chunk.page_numbers[0]) if chunk.page_numbers else "?"
        chunk_text = f"[DOC:{chunk.document_id}:PAGE:{pages_str}]\n{chunk.content}\n"

        chunk_tokens = count_tokens(chunk_text)

        # Stop if adding this chunk would exceed limit
        if current_tokens + chunk_tokens > max_tokens:
            break

        context_parts.append(chunk_text)
        current_tokens += chunk_tokens

    return "\n---\n".join(context_parts)
