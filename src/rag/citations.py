"""Citation validation for RAG answers."""
import re
from uuid import UUID

from .models import ChunkMatch, Citation

CITATION_PATTERN = re.compile(r'\[DOC:([a-f0-9-]{36}):PAGE:(\d+)\]')
NO_INFO_PHRASES = [
    "don't have enough information",
    "cannot answer",
    "not enough context",
    "insufficient information"
]


def extract_citations(answer: str) -> list[tuple[str, int]]:
    """
    Extract all citations from answer text.

    Args:
        answer: Generated answer with citations

    Returns:
        List of (document_id, page_number) tuples
    """
    matches = CITATION_PATTERN.findall(answer)
    return [(doc_id, int(page)) for doc_id, page in matches]


def validate_citations(answer: str, chunks: list[ChunkMatch]) -> bool:
    """
    Validate that all citations in answer reference provided chunks.

    Args:
        answer: Generated answer with citations
        chunks: Chunks used to generate the answer

    Returns:
        True if citations are valid or answer admits lack of information
    """
    citations = extract_citations(answer)

    # If no citations, answer must admit lack of information
    if not citations:
        answer_lower = answer.lower()
        return any(phrase in answer_lower for phrase in NO_INFO_PHRASES)

    # Build set of valid (document_id, page) pairs from chunks
    valid_refs = set()
    for chunk in chunks:
        doc_id_str = str(chunk.document_id)
        for page in chunk.page_numbers:
            valid_refs.add((doc_id_str, page))

    # Verify all citations reference valid chunks
    for doc_id, page in citations:
        if (doc_id, page) not in valid_refs:
            return False

    return True


def build_citations(answer: str, chunks: list[ChunkMatch], document_names: dict[UUID, str]) -> list[Citation]:
    """
    Build citation objects from answer text and chunks.

    Args:
        answer: Generated answer with citations
        chunks: Chunks used to generate the answer
        document_names: Mapping of document_id to filename

    Returns:
        List of Citation objects
    """
    citations = extract_citations(answer)

    # Build mapping from (document_id, page) to chunk content
    chunk_map: dict[tuple[str, int], str] = {}
    for chunk in chunks:
        doc_id_str = str(chunk.document_id)
        for page in chunk.page_numbers:
            key = (doc_id_str, page)
            if key not in chunk_map:
                chunk_map[key] = chunk.content

    # Build unique citations
    seen = set()
    citation_objs = []

    for doc_id, page in citations:
        key = (doc_id, page)
        if key in seen:
            continue
        seen.add(key)

        doc_uuid = UUID(doc_id)
        citation_objs.append(Citation(
            document_id=doc_uuid,
            document_name=document_names.get(doc_uuid, "Unknown Document"),
            page=page,
            snippet=_extract_snippet(chunk_map.get(key, ""), max_length=150)
        ))

    return citation_objs


def _extract_snippet(content: str, max_length: int = 150) -> str:
    """Extract snippet from content, truncating at word boundary."""
    if len(content) <= max_length:
        return content

    truncated = content[:max_length]
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space]

    return truncated + "..."
