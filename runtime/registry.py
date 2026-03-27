from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List

from .guardrails import FoundationRuleError, ensure_company_task_context
from .models import TaskRecord, TaskState


TERMINAL_STATES = {TaskState.DONE.value, TaskState.FAILED.value}


@dataclass(frozen=True)
class SpawnedSessionBinding:
    task_id: str
    session_key: str
    role_id: str


@dataclass(frozen=True)
class CompletionSource:
    task_id: str
    session_key: str | None
    role_id: str | None
    status: str
    summary: str
    next_step: str


@dataclass
class CompanyTaskEntry:
    company_task_id: str
    request_id: str
    line_id: str
    root_task_id: str
    current_task_id: str
    resume_task_id: str
    last_updated_task_id: str
    owner_role_id: str
    session_mode: str
    activation_scope: str
    activation_reason: str
    status: str
    mode_decision: dict
    task_ids: List[str] = field(default_factory=list)
    active_task_ids: List[str] = field(default_factory=list)
    closed_task_ids: List[str] = field(default_factory=list)
    spawned_sessions: List[SpawnedSessionBinding] = field(default_factory=list)
    last_completion_source: CompletionSource | None = None


class CompanyTaskRegistry:
    """Authoritative registry for company-task lineage and continuation.

    The line task board stores task-local state. This registry stores the authoritative
    company-task identity, lineage, and continuation target so the system can answer:
    - which company task is this child task part of?
    - which task was updated most recently?
    - which task should be resumed next?
    - which role / session is currently associated with that work?
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "company-task-registry.json"

    def _load(self) -> dict:
        if not self.path.exists():
            return {"entries": {}, "task_index": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, payload: dict) -> None:
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _entry_from_payload(self, payload: dict) -> CompanyTaskEntry:
        spawned = [SpawnedSessionBinding(**item) for item in payload.get("spawned_sessions", [])]
        completion = payload.get("last_completion_source")
        return CompanyTaskEntry(
            company_task_id=str(payload["company_task_id"]),
            request_id=str(payload["request_id"]),
            line_id=str(payload["line_id"]),
            root_task_id=str(payload["root_task_id"]),
            current_task_id=str(payload["current_task_id"]),
            resume_task_id=str(payload.get("resume_task_id", payload["current_task_id"])),
            last_updated_task_id=str(payload.get("last_updated_task_id", payload["current_task_id"])),
            owner_role_id=str(payload["owner_role_id"]),
            session_mode=str(payload["session_mode"]),
            activation_scope=str(payload["activation_scope"]),
            activation_reason=str(payload["activation_reason"]),
            status=str(payload["status"]),
            mode_decision=dict(payload.get("mode_decision", {})),
            task_ids=list(payload.get("task_ids", [])),
            active_task_ids=list(payload.get("active_task_ids", [])),
            closed_task_ids=list(payload.get("closed_task_ids", [])),
            spawned_sessions=spawned,
            last_completion_source=(CompletionSource(**completion) if completion else None),
        )

    def _entry_to_payload(self, entry: CompanyTaskEntry) -> dict:
        payload = asdict(entry)
        payload["spawned_sessions"] = [asdict(item) for item in entry.spawned_sessions]
        payload["last_completion_source"] = (
            asdict(entry.last_completion_source)
            if entry.last_completion_source is not None
            else None
        )
        return payload

    def _update_entry(self, entry: CompanyTaskEntry) -> CompanyTaskEntry:
        payload = self._load()
        payload["entries"][entry.company_task_id] = self._entry_to_payload(entry)
        for task_id in entry.task_ids:
            payload["task_index"][task_id] = entry.company_task_id
        self._save(payload)
        return entry

    def load_entry(self, company_task_id: str) -> CompanyTaskEntry:
        payload = self._load()
        entry = payload["entries"].get(company_task_id)
        if entry is None:
            raise FoundationRuleError(f"company task not found: {company_task_id}")
        return self._entry_from_payload(entry)

    def create_root_entry(self, task: TaskRecord, *, mode_decision: dict) -> CompanyTaskEntry:
        ensure_company_task_context(task)
        payload = self._load()
        if task.company_task_id in payload["entries"]:
            raise FoundationRuleError(f"company task already exists: {task.company_task_id}")
        entry = CompanyTaskEntry(
            company_task_id=task.company_task_id,
            request_id=task.request_id,
            line_id=task.line_id,
            root_task_id=task.task_id,
            current_task_id=task.task_id,
            resume_task_id=task.task_id,
            last_updated_task_id=task.task_id,
            owner_role_id=task.assigned_to,
            session_mode=task.session_mode,
            activation_scope=task.activation_scope,
            activation_reason=task.activation_reason,
            status=task.state.value,
            mode_decision=dict(mode_decision),
            task_ids=[task.task_id],
            active_task_ids=[task.task_id],
            closed_task_ids=[],
        )
        payload["entries"][task.company_task_id] = self._entry_to_payload(entry)
        payload["task_index"][task.task_id] = task.company_task_id
        self._save(payload)
        return entry

    def register_child_task(self, task: TaskRecord) -> CompanyTaskEntry:
        ensure_company_task_context(task)
        current = self.load_entry(task.company_task_id)
        if task.parent_task_id and task.parent_task_id not in current.task_ids:
            raise FoundationRuleError(
                f"parent task is not registered in company task lineage: {task.parent_task_id}"
            )
        if task.task_id not in current.task_ids:
            current.task_ids.append(task.task_id)
        if task.task_id not in current.active_task_ids and task.state.value not in TERMINAL_STATES:
            current.active_task_ids.append(task.task_id)
        current.current_task_id = task.task_id
        current.resume_task_id = task.task_id
        current.last_updated_task_id = task.task_id
        current.owner_role_id = task.assigned_to
        current.status = task.state.value
        return self._update_entry(current)

    def sync_task(self, task: TaskRecord, *, resume_task_id: str | None = None, owner_role_id: str | None = None) -> CompanyTaskEntry:
        ensure_company_task_context(task)
        current = self.load_entry(task.company_task_id)
        if task.task_id not in current.task_ids:
            current.task_ids.append(task.task_id)
        if task.state.value in TERMINAL_STATES:
            if task.task_id in current.active_task_ids:
                current.active_task_ids.remove(task.task_id)
            if task.task_id not in current.closed_task_ids:
                current.closed_task_ids.append(task.task_id)
        else:
            if task.task_id not in current.active_task_ids:
                current.active_task_ids.append(task.task_id)
            if task.task_id in current.closed_task_ids:
                current.closed_task_ids.remove(task.task_id)
        current.current_task_id = task.task_id
        current.last_updated_task_id = task.task_id
        current.resume_task_id = resume_task_id or task.task_id
        current.owner_role_id = owner_role_id or task.assigned_to
        current.status = task.state.value
        return self._update_entry(current)

    def set_resume_target(self, *, task: TaskRecord, resume_task_id: str, owner_role_id: str) -> CompanyTaskEntry:
        ensure_company_task_context(task)
        current = self.load_entry(task.company_task_id)
        if resume_task_id not in current.task_ids:
            raise FoundationRuleError(
                f"resume task is not registered in company task lineage: {resume_task_id}"
            )
        current.resume_task_id = resume_task_id
        current.owner_role_id = owner_role_id
        current.last_updated_task_id = task.task_id
        current.status = task.state.value
        return self._update_entry(current)

    def bind_spawned_session(self, *, task: TaskRecord, session_key: str, role_id: str) -> CompanyTaskEntry:
        current = self.load_entry(task.company_task_id)
        binding = SpawnedSessionBinding(task_id=task.task_id, session_key=session_key, role_id=role_id)
        if binding not in current.spawned_sessions:
            current.spawned_sessions.append(binding)
        return self._update_entry(current)

    def has_bound_session(self, *, task: TaskRecord, session_key: str, role_id: str | None = None) -> bool:
        current = self.load_entry(task.company_task_id)
        for binding in current.spawned_sessions:
            if binding.task_id != task.task_id:
                continue
            if binding.session_key != session_key:
                continue
            if role_id is not None and binding.role_id != role_id:
                continue
            return True
        return False

    def has_any_bound_session_for_task(self, task: TaskRecord) -> bool:
        current = self.load_entry(task.company_task_id)
        return any(binding.task_id == task.task_id for binding in current.spawned_sessions)

    def record_completion_source(
        self,
        *,
        task: TaskRecord,
        session_key: str | None,
        role_id: str | None,
        status: str,
        summary: str,
        next_step: str,
    ) -> CompanyTaskEntry:
        current = self.load_entry(task.company_task_id)
        current.last_completion_source = CompletionSource(
            task_id=task.task_id,
            session_key=session_key,
            role_id=role_id,
            status=status,
            summary=summary,
            next_step=next_step,
        )
        current.current_task_id = task.task_id
        current.last_updated_task_id = task.task_id
        current.status = task.state.value
        return self._update_entry(current)

    def company_task_for_task(self, task_id: str) -> CompanyTaskEntry:
        payload = self._load()
        company_task_id = payload["task_index"].get(task_id)
        if company_task_id is None:
            raise FoundationRuleError(f"task is not registered in company task registry: {task_id}")
        return self.load_entry(company_task_id)

    def list_entries(self) -> list[CompanyTaskEntry]:
        payload = self._load()
        return [self._entry_from_payload(item) for item in payload["entries"].values()]
