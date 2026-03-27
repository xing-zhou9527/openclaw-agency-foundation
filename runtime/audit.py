from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .guardrails import FoundationRuleError
from .models import BusinessLine, TaskRecord
from .policy import (
    CONTROL_TOWER_ALLOWED_COMMANDS,
    ControlTowerCommand,
    WORKER_ALLOWED_STATUSES,
    WorkerResult,
    validate_control_tower_command,
    validate_worker_result,
)


@dataclass(frozen=True)
class ComplianceIssue:
    code: str
    message: str
    severity: str = "error"


@dataclass
class ComplianceReport:
    subject: str
    ok: bool = True
    issues: list[ComplianceIssue] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add_issue(self, code: str, message: str, severity: str = "error") -> None:
        self.ok = False
        self.issues.append(ComplianceIssue(code=code, message=message, severity=severity))

    def add_note(self, note: str) -> None:
        self.notes.append(note)


def audit_control_tower_command(
    cmd: ControlTowerCommand,
    known_line_ids: Iterable[str] | None = None,
) -> ComplianceReport:
    report = ComplianceReport(subject="control_tower_command")
    known = set(known_line_ids or [])

    try:
        validate_control_tower_command(cmd)
    except FoundationRuleError as exc:
        report.add_issue("control_tower.invalid", str(exc))
        return report

    if known and cmd.line_id not in known:
        report.add_issue("control_tower.unknown_line", f"unknown line id: {cmd.line_id}")

    if cmd.command == "dispatch_line" and not (cmd.next_owner or "").strip():
        report.add_issue(
            "control_tower.missing_next_owner",
            "dispatch_line requires a next_owner (normally the line orchestrator)",
        )

    if cmd.command == "request_line_meeting" and not (cmd.meeting_id or "").strip():
        report.add_issue(
            "control_tower.missing_meeting_id",
            "request_line_meeting requires a meeting_id",
        )

    if cmd.command == "close_task" and not (cmd.task_id or "").strip():
        report.add_issue(
            "control_tower.missing_task_id",
            "close_task requires a task_id",
        )

    if cmd.command not in CONTROL_TOWER_ALLOWED_COMMANDS:
        report.add_issue(
            "control_tower.disallowed_command",
            f"disallowed control tower command: {cmd.command}",
        )

    return report


def coerce_worker_result(payload: str | Mapping[str, Any]) -> WorkerResult:
    if isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = dict(payload)

    artifact_paths = [Path(path) for path in data.get("artifact_paths", [])]
    risks = list(data.get("risks", []))
    return WorkerResult(
        task_id=str(data["task_id"]),
        line_id=str(data["line_id"]),
        role_id=str(data["role_id"]),
        status=str(data["status"]),
        summary=str(data["summary"]),
        next_step=str(data["next_step"]),
        artifact_paths=artifact_paths,
        risks=risks,
    )


def audit_worker_result(
    result: WorkerResult,
    *,
    task: TaskRecord,
    line: BusinessLine,
    reserved_role_ids: Sequence[str] | None = None,
) -> ComplianceReport:
    report = ComplianceReport(subject="worker_result")
    reserved = set(reserved_role_ids or [])
    reserved.add("control-tower")
    reserved.add(line.orchestrator_role_id)

    try:
        validate_worker_result(
            result,
            artifact_root=line.artifact_root,
            allowed_role_ids=line.allowed_role_ids,
            expected_line_id=line.line_id,
        )
    except FoundationRuleError as exc:
        report.add_issue("worker.invalid", str(exc))
        return report

    if result.task_id != task.task_id:
        report.add_issue(
            "worker.task_mismatch",
            f"worker result task mismatch: {result.task_id} != {task.task_id}",
        )

    if result.role_id != task.assigned_to:
        report.add_issue(
            "worker.assignee_mismatch",
            f"worker result role mismatch: {result.role_id} != assigned {task.assigned_to}",
        )

    if result.role_id in reserved:
        report.add_issue(
            "worker.reserved_role",
            f"reserved coordination role cannot be accepted as specialist worker output: {result.role_id}",
        )

    if result.status not in WORKER_ALLOWED_STATUSES:
        report.add_issue(
            "worker.invalid_status",
            f"worker status is outside the accepted set: {result.status}",
        )

    if not result.summary.strip():
        report.add_issue("worker.empty_summary", "worker result summary cannot be empty")

    if not result.next_step.strip():
        report.add_issue("worker.empty_next_step", "worker result next_step cannot be empty")

    for artifact_path in result.artifact_paths:
        try:
            artifact_path.resolve().relative_to(line.artifact_root.resolve())
        except ValueError:
            report.add_issue(
                "worker.artifact_escape",
                f"artifact escapes line root: {artifact_path}",
            )

    return report


def audit_post_run_payload(
    payload: str | Mapping[str, Any],
    *,
    task: TaskRecord,
    line: BusinessLine,
    reserved_role_ids: Sequence[str] | None = None,
) -> ComplianceReport:
    report = ComplianceReport(subject="post_run_payload")
    try:
        result = coerce_worker_result(payload)
    except Exception as exc:  # noqa: BLE001
        report.add_issue("post_run.parse_failed", f"failed to parse worker result: {exc}")
        return report

    nested = audit_worker_result(
        result,
        task=task,
        line=line,
        reserved_role_ids=reserved_role_ids,
    )
    report.ok = nested.ok
    report.issues.extend(nested.issues)
    report.notes.extend(nested.notes)
    if nested.ok:
        report.add_note("post-run payload passed specialist worker audit")
    return report
