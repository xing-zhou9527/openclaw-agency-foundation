from __future__ import annotations

from dataclasses import dataclass

from .guardrails import FoundationRuleError
from .registry import CompanyTaskEntry, CompanyTaskRegistry, TERMINAL_STATES


@dataclass(frozen=True)
class ContinuationRequest:
    request_id: str
    reason: str
    company_task_id: str | None = None
    task_id: str | None = None
    line_id: str | None = None


@dataclass(frozen=True)
class ContinuationResolution:
    request_id: str
    company_task_id: str | None
    line_id: str | None
    current_task_id: str | None
    resume_task_id: str | None
    last_updated_task_id: str | None
    owner_role_id: str | None
    status: str | None
    active_task_ids: tuple[str, ...] = ()
    needs_confirmation: bool = False
    reason: str = ""


def _resolve_by_line(registry: CompanyTaskRegistry, line_id: str) -> CompanyTaskEntry | None:
    candidates = [
        entry
        for entry in registry.list_entries()
        if entry.line_id == line_id and entry.status not in TERMINAL_STATES
    ]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise FoundationRuleError(
            f"continuation is ambiguous for line {line_id}: {len(candidates)} active company tasks"
        )
    return None


def resolve_continuation(
    registry: CompanyTaskRegistry,
    request: ContinuationRequest,
) -> ContinuationResolution:
    if not request.reason.strip():
        raise FoundationRuleError("continuation request requires a non-empty reason")

    entry: CompanyTaskEntry | None = None
    if request.company_task_id:
        entry = registry.load_entry(request.company_task_id)
    elif request.task_id:
        entry = registry.company_task_for_task(request.task_id)
    elif request.line_id:
        entry = _resolve_by_line(registry, request.line_id)
        if entry is None:
            return ContinuationResolution(
                request_id=request.request_id,
                company_task_id=None,
                line_id=request.line_id,
                current_task_id=None,
                resume_task_id=None,
                last_updated_task_id=None,
                owner_role_id=None,
                status=None,
                active_task_ids=(),
                needs_confirmation=True,
                reason=f"no active company task found for line {request.line_id}",
            )
    else:
        raise FoundationRuleError(
            "continuation request requires company_task_id, task_id, or line_id"
        )

    return ContinuationResolution(
        request_id=request.request_id,
        company_task_id=entry.company_task_id,
        line_id=entry.line_id,
        current_task_id=entry.current_task_id,
        resume_task_id=entry.resume_task_id,
        last_updated_task_id=entry.last_updated_task_id,
        owner_role_id=entry.owner_role_id,
        status=entry.status,
        active_task_ids=tuple(entry.active_task_ids),
        needs_confirmation=False,
        reason=request.reason,
    )
