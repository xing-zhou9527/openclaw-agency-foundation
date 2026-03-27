from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from .models import ActorKind, BusinessLine, MeetingRecord, TaskClassSpec, TaskRecord


class FoundationRuleError(ValueError):
    pass


MAIN_CONTROLLER_IDS = {"control_tower", "main_controller", "main_session"}


def ensure_control_tower_is_non_executing(executor_kind: ActorKind) -> None:
    if executor_kind == ActorKind.CONTROL_TOWER:
        raise FoundationRuleError("main-session control tower cannot execute business work")


def ensure_same_line(line: BusinessLine, other_line_id: str) -> None:
    if line.line_id != other_line_id:
        raise FoundationRuleError(
            f"cross-line access denied: {line.line_id} -> {other_line_id}"
        )


def ensure_path_within_root(path: Path, root: Path) -> None:
    path = path.resolve()
    root = root.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise FoundationRuleError(
            f"artifact path escapes line root: {path} not under {root}"
        ) from exc


def ensure_company_task_context(task: TaskRecord) -> None:
    if task.session_mode != "company":
        raise FoundationRuleError(
            f"task is not in company mode and cannot accept control-tower actions: {task.task_id}"
        )
    if not task.company_task_id.strip():
        raise FoundationRuleError(
            f"task is missing company_task_id: {task.task_id}"
        )
    if not task.activation_reason.strip():
        raise FoundationRuleError(
            f"company task is missing activation reason: {task.task_id}"
        )


def ensure_child_task_inherits_company_context(parent: TaskRecord, child: TaskRecord) -> None:
    ensure_company_task_context(parent)
    ensure_company_task_context(child)
    if child.parent_task_id != parent.task_id:
        raise FoundationRuleError(
            f"child task parent mismatch: {child.parent_task_id} != {parent.task_id}"
        )
    if child.company_task_id != parent.company_task_id:
        raise FoundationRuleError(
            f"child task company_task_id mismatch: {child.company_task_id} != {parent.company_task_id}"
        )
    if child.line_id != parent.line_id:
        raise FoundationRuleError(
            f"child task line mismatch: {child.line_id} != {parent.line_id}"
        )
    if child.session_mode != parent.session_mode:
        raise FoundationRuleError(
            f"child task session mode mismatch: {child.session_mode} != {parent.session_mode}"
        )


def ensure_task_assignment_is_legal(task: TaskRecord, allowed_roles: Iterable[str]) -> None:
    if task.assigned_to not in set(allowed_roles):
        raise FoundationRuleError(
            f"role {task.assigned_to} is not allowed in line {task.line_id}"
        )
    if "produce_artifact" in task.allowed_actions and task.assigned_by in MAIN_CONTROLLER_IDS:
        raise FoundationRuleError(
            "main-session control tower cannot assign artifact-producing work directly; line orchestrator must own dispatch"
        )


def require_task_class(line: BusinessLine, task_type: str) -> TaskClassSpec:
    task_class = line.task_classes.get(task_type)
    if task_class is None:
        raise FoundationRuleError(
            f"task_type is not declared in line manifest: {line.line_id}:{task_type}"
        )
    return task_class


def ensure_task_matches_declared_class(
    *,
    line: BusinessLine,
    task_type: str,
    assigned_to: str,
    allowed_actions: Sequence[str],
) -> TaskClassSpec:
    task_class = require_task_class(line, task_type)
    if assigned_to != task_class.default_owner_role_id:
        raise FoundationRuleError(
            f"task_type {task_type} must default to {task_class.default_owner_role_id}, got {assigned_to}"
        )
    if set(allowed_actions) != set(task_class.allowed_actions):
        raise FoundationRuleError(
            f"task_type {task_type} allowed_actions must match manifest declaration"
        )
    role_spec = line.specialists.get(assigned_to)
    if role_spec is None:
        raise FoundationRuleError(
            f"assigned specialist role is not declared in manifest: {assigned_to}"
        )
    if not set(allowed_actions).issubset(set(role_spec.allowed_actions)):
        raise FoundationRuleError(
            f"task_type {task_type} requires actions not allowed for role {assigned_to}"
        )
    return task_class


def ensure_session_registration_allowed(line: BusinessLine) -> None:
    if not line.session_policy.register_spawned_sessions:
        raise FoundationRuleError(
            f"line manifest disables spawned session registration: {line.line_id}"
        )


def ensure_meetings_enabled(line: BusinessLine) -> None:
    if not line.meeting_policy.enabled:
        raise FoundationRuleError(f"meetings are disabled for line: {line.line_id}")
    if not line.meeting_policy.same_line_only:
        raise FoundationRuleError(
            f"line manifest must keep same_line_only=true: {line.line_id}"
        )


def ensure_close_allowed_by_review_policy(line: BusinessLine, task: TaskRecord) -> None:
    task_class = line.task_classes.get(task.task_type)
    if task_class is None:
        return
    if line.review_policy.close_requires_review and task_class.requires_review:
        if task.assigned_to not in set(line.review_policy.reviewer_role_ids):
            raise FoundationRuleError(
                f"task {task.task_id} requires reviewer-owned closure under review policy"
            )


def task_requires_review(line: BusinessLine, task: TaskRecord) -> bool:
    task_class = line.task_classes.get(task.task_type)
    if task_class is None:
        return False
    if task.assigned_to in set(line.review_policy.reviewer_role_ids):
        return False
    return task_class.requires_review


def ensure_meeting_is_same_line(meeting: MeetingRecord, line: BusinessLine) -> None:
    ensure_same_line(line, meeting.line_id)
    participants = set(meeting.participant_role_ids)
    if meeting.moderator_role_id not in {line.meeting_moderator_role_id, line.orchestrator_role_id}:
        raise FoundationRuleError("invalid meeting moderator for line")
    if not participants.issubset(set(line.allowed_role_ids)):
        raise FoundationRuleError("meeting contains role not owned by line")
    if not meeting.company_task_id.startswith(f"company:{line.line_id}:"):
        raise FoundationRuleError("meeting company_task_id does not belong to line")
    if not meeting.task_id.startswith(f"task:{line.line_id}:"):
        raise FoundationRuleError("meeting task_id does not belong to line")


def ensure_artifacts_stay_in_line(task: TaskRecord) -> None:
    for path in task.artifact_paths:
        ensure_path_within_root(path, task.artifact_root)
