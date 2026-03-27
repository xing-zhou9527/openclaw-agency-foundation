from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .guardrails import FoundationRuleError, ensure_path_within_root
from .mode_gate import ActivationScope, SessionMode

CONTROL_TOWER_ALLOWED_COMMANDS = {
    "dispatch_line",
    "request_line_meeting",
    "query_line_status",
    "close_task",
    "escalate",
}

WORKER_ALLOWED_STATUSES = {
    "partial",
    "complete",
    "blocked",
    "needs_review",
    "needs_meeting",
}


@dataclass(frozen=True)
class ControlTowerCommand:
    request_id: str
    command: str
    line_id: str
    reason: str
    task_id: str | None = None
    meeting_id: str | None = None
    next_owner: str | None = None
    status_note: str | None = None
    session_mode: str = SessionMode.COMPANY.value
    activation_reason: str = ""
    activation_scope: str = ActivationScope.REQUEST.value


@dataclass(frozen=True)
class WorkerResult:
    task_id: str
    line_id: str
    role_id: str
    status: str
    summary: str
    next_step: str
    artifact_paths: Sequence[Path]
    risks: Sequence[str] = ()


def validate_control_tower_command(cmd: ControlTowerCommand) -> None:
    if cmd.command not in CONTROL_TOWER_ALLOWED_COMMANDS:
        raise FoundationRuleError(f"control tower command not allowed: {cmd.command}")
    if cmd.session_mode != SessionMode.COMPANY.value:
        raise FoundationRuleError(
            f"control tower command requires session_mode=company, got {cmd.session_mode}"
        )
    if cmd.activation_scope not in {scope.value for scope in ActivationScope}:
        raise FoundationRuleError(
            f"invalid control tower activation scope: {cmd.activation_scope}"
        )
    if not cmd.reason.strip():
        raise FoundationRuleError("control tower command requires a routing reason")
    if not cmd.activation_reason.strip():
        raise FoundationRuleError("control tower command requires an activation reason")
    # The control tower is intentionally forbidden from carrying artifact outputs.
    forbidden_fields = [cmd.next_owner] if cmd.command in {"dispatch_line"} else []
    if any(value is not None and not str(value).strip() for value in forbidden_fields):
        raise FoundationRuleError("control tower command contains malformed dispatch data")


def validate_worker_result(
    result: WorkerResult,
    artifact_root: Path,
    allowed_role_ids: Iterable[str],
    expected_line_id: str,
) -> None:
    if result.line_id != expected_line_id:
        raise FoundationRuleError(
            f"worker result line mismatch: {result.line_id} != {expected_line_id}"
        )
    if result.role_id not in set(allowed_role_ids):
        raise FoundationRuleError(f"worker role not allowed in line: {result.role_id}")
    if result.status not in WORKER_ALLOWED_STATUSES:
        raise FoundationRuleError(f"invalid worker status: {result.status}")
    for path in result.artifact_paths:
        ensure_path_within_root(Path(path), artifact_root)
