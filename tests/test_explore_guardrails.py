from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.auth.models import AuthContext
from src.rag.guardrails import GuardrailViolation, enforce_explore_guardrails
from src.rag.models import AskRequest, GuardrailBypass


def _auth_context(roles: list[str]) -> AuthContext:
    return AuthContext(
        user_id=uuid4(),
        email="admin@example.com",
        tenant_id=uuid4(),
        roles=roles,
        token_exp=datetime.now(timezone.utc) + timedelta(hours=1),
        tenant_slug="demo",
    )


def test_explore_guardrails_require_dataset_scope() -> None:
    auth = _auth_context(["Super Admin"])
    request = AskRequest(
        question="Explore lease economics",
        mode="explore",
        max_chunks=5,
    )

    with pytest.raises(GuardrailViolation, match="guardrails blocked"):
        enforce_explore_guardrails(request, auth)


def test_explore_guardrails_accept_valid_bypass() -> None:
    auth = _auth_context(["Super Admin"])
    dataset_id = uuid4()
    now = datetime.now(timezone.utc)
    bypass = GuardrailBypass(
        requested_by=auth.user_id,
        approved_by=uuid4(),
        approved_by_role="Analytics Tech Lead",
        approved_at=now,
        expires_at=now + timedelta(minutes=30),
        target_user_id=auth.user_id,
        dataset_ids=[dataset_id],
    )
    request = AskRequest(
        question="Explore market rent by tenant type",
        mode="explore",
        document_ids=[dataset_id],
        max_chunks=15,
        guardrail_bypass=bypass,
    )

    assert enforce_explore_guardrails(request, auth) is True


def test_explore_guardrails_rejects_invalid_bypass() -> None:
    auth = _auth_context(["Analyst"])
    dataset_id = uuid4()
    now = datetime.now(timezone.utc)
    bypass = GuardrailBypass(
        requested_by=auth.user_id,
        approved_by=uuid4(),
        approved_by_role="Security Engineer",
        approved_at=now,
        expires_at=now + timedelta(minutes=30),
        target_user_id=auth.user_id,
        dataset_ids=[dataset_id],
    )
    request = AskRequest(
        question="Explore all leases",
        mode="explore",
        document_ids=[dataset_id],
        max_chunks=12,
        guardrail_bypass=bypass,
    )

    with pytest.raises(GuardrailViolation, match="bypass was rejected"):
        enforce_explore_guardrails(request, auth)
