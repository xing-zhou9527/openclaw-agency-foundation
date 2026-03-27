from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .guardrails import FoundationRuleError, ensure_company_task_context
from .models import TaskRecord, TaskState
from .policy import ControlTowerCommand


ALLOWED_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.INBOX: {TaskState.ASSIGNED, TaskState.FAILED},
    TaskState.ASSIGNED: {TaskState.IN_PROGRESS, TaskState.MEETING, TaskState.BLOCKED, TaskState.FAILED},
    TaskState.IN_PROGRESS: {TaskState.MEETING, TaskState.REVIEW, TaskState.DONE, TaskState.BLOCKED, TaskState.FAILED},
    TaskState.MEETING: {TaskState.IN_PROGRESS, TaskState.REVIEW, TaskState.BLOCKED, TaskState.FAILED},
    TaskState.REVIEW: {TaskState.DONE, TaskState.IN_PROGRESS, TaskState.BLOCKED, TaskState.FAILED},
    TaskState.BLOCKED: {TaskState.ASSIGNED, TaskState.FAILED},
    TaskState.DONE: set(),
    TaskState.FAILED: set(),
}

CONTROL_TOWER_ALLOWED_BY_STATE: dict[TaskState, set[str]] = {
    TaskState.INBOX: {"dispatch_line", "escalate"},
    TaskState.ASSIGNED: {"query_line_status", "request_line_meeting", "escalate"},
    TaskState.IN_PROGRESS: {"query_line_status", "request_line_meeting", "escalate"},
    TaskState.MEETING: {"query_line_status", "escalate"},
    TaskState.REVIEW: {"query_line_status", "close_task", "escalate"},
    TaskState.BLOCKED: {"query_line_status", "request_line_meeting", "escalate", "close_task"},
    TaskState.DONE: {"query_line_status"},
    TaskState.FAILED: {"query_line_status"},
}


def serialize_task(task: TaskRecord) -> dict:
    payload = asdict(task)
    payload["state"] = task.state.value
    payload["artifact_root"] = str(task.artifact_root)
    payload["artifact_paths"] = [str(path) for path in task.artifact_paths]
    return payload


def deserialize_task(payload: dict) -> TaskRecord:
    return TaskRecord(
        task_id=str(payload["task_id"]),
        company_task_id=str(payload["company_task_id"]),
        request_id=str(payload["request_id"]),
        line_id=str(payload["line_id"]),
        requested_by=str(payload["requested_by"]),
        assigned_by=str(payload["assigned_by"]),
        assigned_to=str(payload["assigned_to"]),
        task_type=str(payload["task_type"]),
        state=TaskState(str(payload["state"])),
        allowed_actions=list(payload.get("allowed_actions", [])),
        artifact_root=Path(payload["artifact_root"]),
        artifact_paths=[Path(path) for path in payload.get("artifact_paths", [])],
        parent_task_id=(
            str(payload["parent_task_id"])
            if payload.get("parent_task_id") is not None
            else None
        ),
        session_mode=str(payload.get("session_mode", "company")),
        activation_reason=str(payload.get("activation_reason", "")),
        activation_scope=str(payload.get("activation_scope", "request")),
    )


class LineTaskBoard:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _task_dir(self, task_id: str) -> Path:
        safe = task_id.replace(":", "__")
        return self.root / safe

    def _task_file(self, task_id: str) -> Path:
        return self._task_dir(task_id) / "task.json"

    def _events_file(self, task_id: str) -> Path:
        return self._task_dir(task_id) / "events.jsonl"

    def save_task(self, task: TaskRecord) -> None:
        task_dir = self._task_dir(task.task_id)
        task_dir.mkdir(parents=True, exist_ok=True)
        self._task_file(task.task_id).write_text(
            json.dumps(serialize_task(task), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_task(self, task_id: str) -> TaskRecord:
        path = self._task_file(task_id)
        if not path.exists():
            raise FoundationRuleError(f"task not found: {task_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return deserialize_task(payload)

    def append_event(self, task_id: str, event: dict) -> None:
        task_dir = self._task_dir(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)
        with self._events_file(task_id).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    def create_task(self, task: TaskRecord, note: str | None = None) -> TaskRecord:
        if self._task_file(task.task_id).exists():
            raise FoundationRuleError(f"task already exists: {task.task_id}")
        self.save_task(task)
        self.append_event(
            task.task_id,
            {
                "kind": "task_created",
                "task_id": task.task_id,
                "company_task_id": task.company_task_id,
                "parent_task_id": task.parent_task_id,
                "state": task.state.value,
                "session_mode": task.session_mode,
                "activation_scope": task.activation_scope,
                "note": note or "",
            },
        )
        return task

    def transition(self, task_id: str, new_state: TaskState, note: str = "") -> TaskRecord:
        task = self.load_task(task_id)
        allowed = ALLOWED_TRANSITIONS.get(task.state, set())
        if new_state not in allowed:
            raise FoundationRuleError(
                f"illegal task transition: {task.state.value} -> {new_state.value}"
            )
        updated = TaskRecord(
            task_id=task.task_id,
            company_task_id=task.company_task_id,
            request_id=task.request_id,
            line_id=task.line_id,
            requested_by=task.requested_by,
            assigned_by=task.assigned_by,
            assigned_to=task.assigned_to,
            task_type=task.task_type,
            state=new_state,
            allowed_actions=task.allowed_actions,
            artifact_root=task.artifact_root,
            artifact_paths=task.artifact_paths,
            parent_task_id=task.parent_task_id,
            session_mode=task.session_mode,
            activation_reason=task.activation_reason,
            activation_scope=task.activation_scope,
        )
        self.save_task(updated)
        self.append_event(
            task_id,
            {
                "kind": "task_transition",
                "from": task.state.value,
                "to": new_state.value,
                "note": note,
            },
        )
        return updated

    def update_artifacts(self, task_id: str, artifact_paths: Iterable[Path], note: str = "") -> TaskRecord:
        task = self.load_task(task_id)
        merged = list(dict.fromkeys([*task.artifact_paths, *artifact_paths]))
        updated = TaskRecord(
            task_id=task.task_id,
            company_task_id=task.company_task_id,
            request_id=task.request_id,
            line_id=task.line_id,
            requested_by=task.requested_by,
            assigned_by=task.assigned_by,
            assigned_to=task.assigned_to,
            task_type=task.task_type,
            state=task.state,
            allowed_actions=task.allowed_actions,
            artifact_root=task.artifact_root,
            artifact_paths=merged,
            parent_task_id=task.parent_task_id,
            session_mode=task.session_mode,
            activation_reason=task.activation_reason,
            activation_scope=task.activation_scope,
        )
        self.save_task(updated)
        self.append_event(
            task_id,
            {
                "kind": "task_artifacts_updated",
                "artifact_paths": [str(path) for path in merged],
                "note": note,
            },
        )
        return updated

    def assert_control_tower_command_allowed(self, task: TaskRecord, cmd: ControlTowerCommand) -> None:
        ensure_company_task_context(task)
        if cmd.session_mode != task.session_mode:
            raise FoundationRuleError(
                f"control tower command mode mismatch: {cmd.session_mode} != {task.session_mode}"
            )
        allowed = CONTROL_TOWER_ALLOWED_BY_STATE.get(task.state, set())
        if cmd.command not in allowed:
            raise FoundationRuleError(
                f"control tower command {cmd.command} is not allowed when task state is {task.state.value}"
            )
