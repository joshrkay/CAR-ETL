"""
Ask Routes - RAG Q&A Endpoints

Handles question answering with mandatory citations.
"""

import inspect
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from supabase import Client

from src.auth.models import AuthContext
from src.auth.decorators import require_permission
from src.dependencies import get_current_user, get_supabase_client
from src.search.embeddings import EmbeddingService
from src.rag.pipeline import RAGPipeline
from src.rag.generator import Generator
from src.rag.models import AskRequest, AskResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["ask"],
)


def _permission_dependency(permission: str):
    async def dependency(request: Request) -> AuthContext:
        checker = require_permission(permission)
        parameters = inspect.signature(checker).parameters
        if parameters and all(
            param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            for param in parameters.values()
        ):
            result = checker()
        elif len(parameters) >= 2:
            auth = get_current_user(request)
            result = checker(request, auth)
        elif len(parameters) == 1:
            result = checker(request)
        else:
            result = checker()
        if inspect.isawaitable(result):
            return await result
        return result

    return dependency


def _supabase_dependency(request: Request) -> Client:
    return get_supabase_client(request)


@router.post(
    "/ask",
    response_model=AskResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask question about documents",
    description="""
    Ask a question about your documents and receive an answer with mandatory citations.

    Security:
    - Requires authentication and 'documents:read' permission
    - Tenant isolation enforced via RLS
    - Only searches documents within your tenant

    RAG Pipeline:
    1. Embeds your question
    2. Retrieves top-20 relevant chunks
    3. Re-ranks to top-max_chunks most relevant (default 5, range 1-20)
    4. Builds context for LLM
    5. Generates answer with citations
    6. Validates all citations

    Citation Format:
    - All factual claims include citations: [DOC:uuid:PAGE:n]
    - Citations link to specific pages in source documents
    - If answer cannot be found, returns suggestion

    Filters:
    - Optionally filter to specific documents via document_ids
    - Control number of chunks used via max_chunks (1-20)
    """,
)
async def ask_question(
    request: Request,
    ask_request: AskRequest,
    auth: AuthContext = Depends(_permission_dependency("documents:read")),
    supabase: Client = Depends(_supabase_dependency),
) -> AskResponse:
    """
    Answer question about documents with citations.

    Args:
        request: FastAPI request object
        ask_request: Question request with filters
        auth: Authenticated user context
        supabase: Supabase client with user JWT

    Returns:
        AskResponse with answer and citations

    Raises:
        HTTPException 400: Invalid request
        HTTPException 401: User not authenticated
        HTTPException 403: Insufficient permissions
        HTTPException 500: Server error
    """
    request_id = getattr(request.state, "request_id", "unknown")
    tenant_id = str(auth.tenant_id)
    user_id = str(auth.user_id)

    logger.info(
        "Question asked",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "question_length": len(ask_request.question),
            "document_filter": bool(ask_request.document_ids),
            "max_chunks": ask_request.max_chunks,
        },
    )

    try:
        # Initialize RAG pipeline components
        embedding_service = EmbeddingService()
        generator = Generator()
        pipeline = RAGPipeline(supabase, embedding_service, generator)

        # Process question
        response = await pipeline.ask(ask_request)

        logger.info(
            "Question answered",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "chunks_used": response.chunks_used,
                "citations_count": len(response.citations),
                "confidence": response.confidence,
            },
        )

        return response

    except ValueError as e:
        logger.error(
            "Invalid request",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "Failed to answer question",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process question",
        )
