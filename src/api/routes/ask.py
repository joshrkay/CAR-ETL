"""
Ask Routes - RAG Q&A Endpoints

Handles question answering with mandatory citations.
"""

import inspect
import logging
from datetime import datetime, timezone
from typing import Any, Callable, cast
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, status
from supabase import Client

from src.auth.models import AuthContext
from src.auth.decorators import require_permission
from src.dependencies import get_current_user, get_supabase_client
from src.search.embeddings import EmbeddingService
from src.audit.logger import AuditLogger
from src.audit.models import ActionType, EventType
from src.rag.context_builder import ContextLimitError
from src.rag.guardrails import GuardrailViolation, enforce_explore_guardrails
from src.rag.pipeline import RAGPipeline
from src.rag.generator import Generator
from src.rag.models import AskRequest, AskResponse, GuardrailBypass

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["ask"],
)


def _permission_dependency(permission: str) -> Callable[[Request], Any]:
    async def dependency(request: Request) -> AuthContext:
        checker: Any = require_permission(permission)
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
            return cast(AuthContext, await result)
        return cast(AuthContext, result)

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
            "mode": ask_request.mode,
        },
    )

    try:
        bypass_used = False
        dataset_names = []
        if ask_request.mode == "explore":
            dataset_names = _resolve_dataset_names(supabase, ask_request.document_ids or [])
            exception_bypass = _load_guardrail_exception(
                supabase=supabase,
                auth=auth,
                ask_request=ask_request,
                dataset_names=dataset_names,
            )
            if exception_bypass:
                ask_request.guardrail_bypass = exception_bypass

            bypass_used = enforce_explore_guardrails(ask_request, auth)
            if bypass_used:
                await _log_guardrail_bypass(
                    request,
                    auth,
                    ask_request,
                    dataset_names=dataset_names,
                    query_id=request_id,
                )
                if not (ask_request.guardrail_bypass and ask_request.guardrail_bypass.from_exception):
                    await _record_guardrail_exception(
                        request,
                        auth,
                        ask_request,
                        dataset_names=dataset_names,
                        query_id=request_id,
                    )

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

    except GuardrailViolation as e:
        logger.warning(
            "Explore guardrails blocked query",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "violations": e.violations,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_detail(),
        )
    except ContextLimitError as e:
        logger.warning(
            "Explore context exceeded token limit",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "GUARDRAIL_VIOLATION",
                "message": str(e),
                "violations": [str(e)],
            },
        )
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


async def _log_guardrail_bypass(
    request: Request,
    auth: AuthContext,
    ask_request: AskRequest,
    dataset_names: list[str],
    query_id: str,
) -> None:
    try:
        supabase = get_supabase_client(request)
    except Exception:
        logger.warning("Failed to log guardrail bypass: no Supabase client available")
        return

    audit_logger = AuditLogger(
        supabase=supabase,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
    )
    bypass = ask_request.guardrail_bypass
    timestamp = datetime.now(timezone.utc)
    duration_minutes = _duration_minutes(bypass) if bypass else None
    metadata = {
        "mode": "explore",
        "user_id": str(auth.user_id),
        "dataset_count": len(ask_request.document_ids or []),
        "dataset_ids": [str(doc_id) for doc_id in (ask_request.document_ids or [])],
        "dataset_names": dataset_names,
        "timestamp": timestamp.isoformat(),
        "query_id": query_id,
        "requestor": str(auth.user_id),
        "user": str(auth.user_id),
    }
    if bypass:
        metadata.update(
            {
                "approver": str(bypass.approved_by),
                "approved_by": str(bypass.approved_by),
                "approved_by_role": bypass.approved_by_role,
                "expires_at": bypass.expires_at.isoformat(),
                "duration_minutes": duration_minutes,
                "reason": bypass.reason,
            }
        )
    await audit_logger.log(
        event_type=EventType.EXPLORE_GUARDRAIL_BYPASS,
        action=ActionType.READ,
        resource_type="explore",
        resource_id="ask",
        metadata=metadata,
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await audit_logger.flush()


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def _record_guardrail_exception(
    request: Request,
    auth: AuthContext,
    ask_request: AskRequest,
    dataset_names: list[str],
    query_id: str,
) -> None:
    bypass = ask_request.guardrail_bypass
    if not bypass:
        return

    try:
        supabase = get_supabase_client(request)
    except Exception:
        logger.warning("Failed to record guardrail exception: no Supabase client available")
        return

    if not dataset_names:
        dataset_names = _resolve_dataset_names(supabase, ask_request.document_ids or [])

    existing_exception = _find_matching_exception(
        supabase=supabase,
        auth=auth,
        dataset_names=dataset_names,
    )
    if existing_exception:
        return

    now = datetime.now(timezone.utc)
    expires_at = bypass.expires_at
    duration_minutes = _duration_minutes(bypass)

    supabase.table("explore_guardrail_exceptions").insert(
        {
            "id": str(uuid4()),
            "user_id": str(auth.user_id),
            "approved_by": str(bypass.approved_by),
            "dataset_names": dataset_names,
            "expires_at": expires_at.isoformat(),
            "reason": bypass.reason,
        }
    ).execute()

    await _log_guardrail_exception_event(
        request=request,
        supabase=supabase,
        auth=auth,
        ask_request=ask_request,
        dataset_names=dataset_names,
        query_id=query_id,
        event_type=EventType.EXPLORE_GUARDRAIL_EXCEPTION_CREATED,
        timestamp=now,
        duration_minutes=duration_minutes,
    )
    await _log_guardrail_exception_event(
        request=request,
        supabase=supabase,
        auth=auth,
        ask_request=ask_request,
        dataset_names=dataset_names,
        query_id=query_id,
        event_type=EventType.EXPLORE_GUARDRAIL_EXCEPTION_APPROVED,
        timestamp=now,
        duration_minutes=duration_minutes,
    )


def _resolve_dataset_names(supabase: Client, document_ids: list[UUID]) -> list[str]:
    if not document_ids:
        return []

    response = (
        supabase.table("documents")
        .select("id, original_filename")
        .in_("id", [str(doc_id) for doc_id in document_ids])
        .execute()
    )
    names_by_id = {
        UUID(row["id"]): row.get("original_filename", "Unknown") for row in response.data or []
    }
    return [names_by_id.get(doc_id, "Unknown") for doc_id in document_ids]


def _load_guardrail_exception(
    supabase: Client,
    auth: AuthContext,
    ask_request: AskRequest,
    dataset_names: list[str],
) -> GuardrailBypass | None:
    if not dataset_names:
        return None

    exception = _find_matching_exception(
        supabase=supabase,
        auth=auth,
        dataset_names=dataset_names,
    )
    if not exception:
        return None

    approved_by = exception.get("approved_by")
    if approved_by is None:
        return None

    expires_at = _parse_datetime(exception.get("expires_at"))
    approved_at = _parse_datetime(exception.get("created_at"))
    return _build_exception_bypass(
        auth=auth,
        ask_request=ask_request,
        approved_by=approved_by,
        approved_at=approved_at,
        expires_at=expires_at,
        reason=exception.get("reason"),
    )


def _find_matching_exception(
    supabase: Client,
    auth: AuthContext,
    dataset_names: list[str],
) -> dict[str, object] | None:
    now_iso = datetime.now(timezone.utc).isoformat()
    response = (
        supabase.table("explore_guardrail_exceptions")
        .select("id, user_id, approved_by, dataset_names, expires_at, reason, created_at")
        .eq("user_id", str(auth.user_id))
        .gt("expires_at", now_iso)
        .execute()
    )
    if not response.data:
        return None

    requested = set(dataset_names)
    for row in response.data:
        approved_names = set(row.get("dataset_names") or [])
        if requested.issubset(approved_names):
            return row
    return None


def _build_exception_bypass(
    auth: AuthContext,
    ask_request: AskRequest,
    approved_by: object,
    approved_at: datetime,
    expires_at: datetime,
    reason: object,
) -> GuardrailBypass:
    return GuardrailBypass(
        requested_by=auth.user_id,
        approved_by=_parse_uuid(approved_by),
        approved_by_role="approved_exception",
        approved_at=approved_at,
        expires_at=expires_at,
        target_user_id=auth.user_id,
        dataset_ids=ask_request.document_ids or [],
        reason=str(reason),
        from_exception=True,
    )


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _parse_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _duration_minutes(bypass: GuardrailBypass | None) -> int | None:
    if not bypass:
        return None
    duration = bypass.expires_at - bypass.approved_at
    return max(int(duration.total_seconds() / 60), 0)


async def _log_guardrail_exception_event(
    request: Request,
    supabase: Client,
    auth: AuthContext,
    ask_request: AskRequest,
    dataset_names: list[str],
    query_id: str,
    event_type: EventType,
    timestamp: datetime,
    duration_minutes: int | None,
) -> None:
    bypass = ask_request.guardrail_bypass
    if not bypass:
        return

    audit_logger = AuditLogger(
        supabase=supabase,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
    )
    metadata = {
        "requestor": str(bypass.requested_by),
        "approver": str(bypass.approved_by),
        "user": str(auth.user_id),
        "dataset_ids": [str(doc_id) for doc_id in (ask_request.document_ids or [])],
        "dataset_names": dataset_names,
        "duration_minutes": duration_minutes,
        "expires_at": bypass.expires_at.isoformat(),
        "reason": bypass.reason,
        "timestamp": timestamp.isoformat(),
        "query_id": query_id,
    }
    await audit_logger.log(
        event_type=event_type,
        action=ActionType.CREATE,
        resource_type="explore",
        resource_id="guardrail_exception",
        metadata=metadata,
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await audit_logger.flush()
