"""Guardrails for explore mode queries."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List

from src.auth.models import AuthContext
from src.rag.models import AskRequest, GuardrailBypass


MAX_EXPLORE_DOCUMENTS = 25
MAX_EXPLORE_CHUNKS = 10
MAX_EXPLORE_QUESTION_LENGTH = 500
MAX_BYPASS_MINUTES = 60
REQUIRED_REQUESTER_ROLE = "super admin"
ALLOWED_APPROVER_ROLES = {"analytics tech lead", "security engineer"}


@dataclass(frozen=True)
class GuardrailViolation(Exception):
    """Raised when explore guardrails are violated."""

    message: str
    violations: List[str]

    def to_detail(self) -> dict:
        """Serialize violation for API response."""
        return {
            "code": "GUARDRAIL_VIOLATION",
            "message": self.message,
            "violations": self.violations,
        }


def enforce_explore_guardrails(request: AskRequest, auth: AuthContext) -> bool:
    """
    Enforce explore mode guardrails.

    Returns True if a bypass was validated (and thus used).
    Raises GuardrailViolation if guardrails fail without an approved bypass.
    """
    if request.mode != "explore":
        return False

    violations = _collect_guardrail_violations(request)
    bypass = request.guardrail_bypass

    if bypass:
        _validate_bypass(bypass=bypass, auth=auth, request=request)
        if violations:
            return True
        return True

    if violations:
        raise GuardrailViolation(
            message="Explore mode guardrails blocked this query.",
            violations=violations,
        )

    return False


def _collect_guardrail_violations(request: AskRequest) -> List[str]:
    violations: List[str] = []
    if not request.document_ids:
        violations.append("Explore mode requires at least one dataset (document_ids).")
    elif len(request.document_ids) > MAX_EXPLORE_DOCUMENTS:
        violations.append(
            f"Explore mode allows up to {MAX_EXPLORE_DOCUMENTS} datasets per query."
        )

    if len(request.question) > MAX_EXPLORE_QUESTION_LENGTH:
        violations.append(
            f"Explore mode questions must be {MAX_EXPLORE_QUESTION_LENGTH} characters or fewer."
        )

    if request.max_chunks > MAX_EXPLORE_CHUNKS:
        violations.append(
            f"Explore mode allows up to {MAX_EXPLORE_CHUNKS} chunks per query."
        )

    return violations


def _validate_bypass(bypass: GuardrailBypass, auth: AuthContext, request: AskRequest) -> None:
    violations: List[str] = []
    now = datetime.now(timezone.utc)

    if REQUIRED_REQUESTER_ROLE not in _normalize_roles(auth.roles):
        violations.append("Only Super Admin can request a guardrail bypass.")

    if bypass.requested_by != auth.user_id:
        violations.append("Bypass requester must match the authenticated user.")

    if bypass.target_user_id != auth.user_id:
        violations.append("Bypass target user must match the authenticated user.")

    if _normalize_role(bypass.approved_by_role) not in ALLOWED_APPROVER_ROLES:
        violations.append(
            "Guardrail bypass requires approval by Analytics Tech Lead or Security Engineer."
        )

    if bypass.approved_at > now:
        violations.append("Bypass approval time cannot be in the future.")

    if bypass.expires_at <= now:
        violations.append("Guardrail bypass has expired.")

    if bypass.expires_at - bypass.approved_at > timedelta(minutes=MAX_BYPASS_MINUTES):
        violations.append(
            f"Guardrail bypass duration must be {MAX_BYPASS_MINUTES} minutes or less."
        )

    if not bypass.dataset_ids:
        violations.append("Bypass scope must include at least one dataset.")

    if not request.document_ids:
        violations.append("Bypass requires dataset scoping via document_ids.")
    else:
        request_ids = set(request.document_ids)
        bypass_ids = set(bypass.dataset_ids)
        if not request_ids.issubset(bypass_ids):
            violations.append("Requested datasets are outside the approved bypass scope.")

    if violations:
        raise GuardrailViolation(
            message="Guardrail bypass was rejected.",
            violations=violations,
        )


def _normalize_role(role: str) -> str:
    return role.strip().lower()


def _normalize_roles(roles: List[str]) -> set[str]:
    return {_normalize_role(role) for role in roles}
