from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .audit import ComplianceReport, audit_post_run_payload, coerce_worker_result
from .continuation import ContinuationRequest, ContinuationResolution, resolve_continuation
from .deployment import load_deployment_manifest, resolve_deployment_layout
from .dispatch import ControlTowerDispatcher, command_to_payload
from .guardrails import (
    FoundationRuleError,
    ensure_child_task_inherits_company_context,
    ensure_close_allowed_by_review_policy,
    ensure_company_task_context,
    ensure_meetings_enabled,
    ensure_session_registration_allowed,
    ensure_task_assignment_is_legal,
    ensure_task_matches_declared_class,
    task_requires_review,
)
from .line_loader import (
    load_business_line_from_manifest_path,
    load_business_lines_from_manifest_root,
)
from .meetingboard import LineMeetingBoard
from .meetings import open_meeting
from .mode_gate import ModeDecision, ensure_company_mode_active, mode_decision_to_payload
from .models import BusinessLine, MeetingRecord, TaskRecord, TaskState
from .registry import CompanyTaskRegistry
from .router import build_line_template, company_task_id, task_id
from .taskboard import LineTaskBoard


@dataclass(frozen=True)
class RoutedTask:
    command: dict
    task: TaskRecord


@dataclass(frozen=True)
class MeetingDispatch:
    command: dict
    task: TaskRecord
    meeting: MeetingRecord


@dataclass(frozen=True)
class MeetingOutcomeResult:
    task: TaskRecord
    meeting: MeetingRecord


class FoundationEngine:
    """Execution adapter for the main-session control tower.

    The main session has two planes:
    - normal assistant mode for ordinary chat / coding / meta work
    - company mode for line-owned operational execution

    All control-tower actions in company mode must enter through this engine.
    The engine forces mode-gate validation before routing, dispatcher validation on
    outbound commands, and audit validation on inbound worker completion payloads.

    It also maintains an authoritative company-task registry so continuation and
    worker-completion events can be tied back to the correct task lineage.
    """

    def __init__(
        self,
        *,
        state_root: Path,
        lines: Mapping[str, BusinessLine],
        registry_root: Path | None = None,
    ):
        self.state_root = Path(state_root)
        self.registry_root = Path(registry_root or (self.state_root / "registry"))
        self.lines = dict(lines)
        self.dispatcher = ControlTowerDispatcher(self.lines)
        self.taskboards = {
            line_id: LineTaskBoard(line.task_root) for line_id, line in self.lines.items()
        }
        self.meetingboards = {
            line_id: LineMeetingBoard(line.meeting_root) for line_id, line in self.lines.items()
        }
        self.registry = CompanyTaskRegistry(self.registry_root)

    @classmethod
    def from_deployment(
        cls,
        *,
        line_ids: Iterable[str],
        home: Path | str | None = None,
        manifest_root: Path | str | None = None,
        state_root: Path | str | None = None,
        lines_root: Path | str | None = None,
        registry_root: Path | str | None = None,
    ) -> "FoundationEngine":
        layout = resolve_deployment_layout(
            home=home,
            manifest_root=manifest_root,
            state_root=state_root,
            lines_root=lines_root,
            registry_root=registry_root,
        )
        lines = {
            line_id: build_line_template(layout.lines_root, line_id) for line_id in line_ids
        }
        return cls(
            state_root=layout.state_root,
            registry_root=layout.registry_root,
            lines=lines,
        )

    @classmethod
    def from_manifest_dir(
        cls,
        *,
        line_ids: Iterable[str] | None = None,
        home: Path | str | None = None,
        manifest_root: Path | str | None = None,
        state_root: Path | str | None = None,
        lines_root: Path | str | None = None,
        registry_root: Path | str | None = None,
    ) -> "FoundationEngine":
        """Load business lines from external manifest assets.

        This is the intended initialization path for real deployments:
        - line definitions come from external line packs under `~/.gency/line-packs`
        - runtime state lives under `~/.gency/state`
        - the foundation repo remains product code only
        """

        layout = resolve_deployment_layout(
            home=home,
            manifest_root=manifest_root,
            state_root=state_root,
            lines_root=lines_root,
            registry_root=registry_root,
        )
        lines = load_business_lines_from_manifest_root(
            layout.manifest_root,
            lines_root=layout.lines_root,
            line_ids=line_ids,
        )
        return cls(
            state_root=layout.state_root,
            registry_root=layout.registry_root,
            lines=lines,
        )

    @classmethod
    def from_deployment_manifest(
        cls,
        *,
        manifest_path: Path | str | None = None,
        home: Path | str | None = None,
        manifest_root: Path | str | None = None,
        state_root: Path | str | None = None,
        lines_root: Path | str | None = None,
        registry_root: Path | str | None = None,
        line_ids: Iterable[str] | None = None,
    ) -> "FoundationEngine":
        """Load a deployment manifest and initialize the engine from it.

        Intended first-class public boundary:
        - deployment manifest (default `~/.gency/deployment.json`)
        - line packs under `~/.gency/line-packs`
        - runtime state under `~/.gency/state`
        """

        deployment_manifest = load_deployment_manifest(
            manifest_path=manifest_path,
            home=home,
        )
        payload = deployment_manifest.payload
        layout = resolve_deployment_layout(
            home=home,
            manifest_root=manifest_root,
            state_root=state_root,
            lines_root=lines_root,
            registry_root=registry_root,
            defaults=payload,
        )
        manifest_enabled_lines = list(payload.get("enabled_lines", []))
        enabled_lines = list(line_ids) if line_ids is not None else manifest_enabled_lines
        if line_ids is not None:
            unknown_line_ids = sorted(set(enabled_lines) - set(manifest_enabled_lines))
            if unknown_line_ids:
                raise FoundationRuleError(
                    f"requested line_ids are not enabled in deployment manifest: {', '.join(unknown_line_ids)}"
                )
        if not enabled_lines:
            raise FoundationRuleError(
                f"deployment manifest must define enabled_lines: {deployment_manifest.path}"
            )

        manifest_files = payload.get("line_manifest_files", {})
        if manifest_files and not isinstance(manifest_files, dict):
            raise FoundationRuleError(
                f"deployment manifest line_manifest_files must be an object: {deployment_manifest.path}"
            )

        lines: dict[str, BusinessLine] = {}
        for line_id in enabled_lines:
            explicit_manifest = manifest_files.get(line_id) if isinstance(manifest_files, dict) else None
            if explicit_manifest:
                explicit_manifest_path = Path(str(explicit_manifest)).expanduser()
                if not explicit_manifest_path.is_absolute():
                    explicit_manifest_path = deployment_manifest.path.parent / explicit_manifest_path
                lines[line_id] = load_business_line_from_manifest_path(
                    explicit_manifest_path,
                    lines_root=layout.lines_root,
                )
            else:
                lines.update(
                    load_business_lines_from_manifest_root(
                        layout.manifest_root,
                        lines_root=layout.lines_root,
                        line_ids=[line_id],
                    )
                )
        return cls(
            state_root=layout.state_root,
            registry_root=layout.registry_root,
            lines=lines,
        )

    @classmethod
    def from_line_ids(
        cls,
        *,
        line_ids: Iterable[str],
        base_dir: Path | str | None = None,
        state_root: Path | str | None = None,
        lines_root: Path | str | None = None,
        registry_root: Path | str | None = None,
        home: Path | str | None = None,
    ) -> "FoundationEngine":
        """Compatibility helper for smoke/demo flows.

        This helper still synthesizes line templates from a lines root, but real
        deployments should treat line/role assets as external workdir content under
        `~/.gency` (or env-overridden roots), not as foundation-repo state.
        """

        if state_root is None and base_dir is not None:
            state_root = base_dir
        return cls.from_deployment(
            line_ids=line_ids,
            home=home,
            state_root=state_root,
            lines_root=lines_root,
            registry_root=registry_root,
        )

    def require_line(self, line_id: str) -> BusinessLine:
        line = self.lines.get(line_id)
        if line is None:
            raise FoundationRuleError(f"unknown business line: {line_id}")
        return line

    def board(self, line_id: str) -> LineTaskBoard:
        board = self.taskboards.get(line_id)
        if board is None:
            raise FoundationRuleError(f"no task board for line: {line_id}")
        return board

    def meeting_board(self, line_id: str) -> LineMeetingBoard:
        board = self.meetingboards.get(line_id)
        if board is None:
            raise FoundationRuleError(f"no meeting board for line: {line_id}")
        return board

    def route_request(
        self,
        *,
        mode: ModeDecision,
        request_id: str,
        line_id: str,
        task_local_id: str,
        reason: str,
        requested_by: str = "user",
    ) -> RoutedTask:
        ensure_company_mode_active(mode, expected_line_id=line_id)
        line = self.require_line(line_id)
        board = self.board(line_id)
        mode_payload = mode_decision_to_payload(mode)
        task = TaskRecord(
            task_id=task_id(line_id, task_local_id),
            company_task_id=company_task_id(line_id, task_local_id),
            request_id=request_id,
            line_id=line_id,
            requested_by=requested_by,
            assigned_by="control-tower",
            assigned_to=line.orchestrator_role_id,
            task_type="route",
            state=TaskState.INBOX,
            allowed_actions=["dispatch", "request_meeting", "close_task", "escalate"],
            artifact_root=line.artifact_root,
            artifact_paths=[],
            parent_task_id=None,
            session_mode=mode.session_mode.value,
            activation_reason=mode.reason,
            activation_scope=mode.scope.value,
        )
        board.create_task(task, note=reason)
        self.registry.create_root_entry(task, mode_decision=mode_payload)
        board.append_event(
            task.task_id,
            {
                "kind": "mode_gate_decision",
                "payload": mode_payload,
            },
        )
        cmd = self.dispatcher.dispatch_line(
            request_id=request_id,
            line_id=line_id,
            task_id=task.task_id,
            reason=reason,
            next_owner=line.orchestrator_role_id,
            activation_reason=mode.reason,
            activation_scope=mode.scope.value,
        )
        board.assert_control_tower_command_allowed(task, cmd)
        updated = board.transition(task.task_id, TaskState.ASSIGNED, note="routed to line orchestrator")
        self.registry.sync_task(updated, resume_task_id=updated.task_id, owner_role_id=updated.assigned_to)
        board.append_event(
            task.task_id,
            {
                "kind": "control_tower_command",
                "payload": command_to_payload(cmd),
            },
        )
        return RoutedTask(command=command_to_payload(cmd), task=updated)

    def resolve_continuation(
        self,
        *,
        mode: ModeDecision,
        request_id: str,
        reason: str,
        company_task_id_value: str | None = None,
        task_id_value: str | None = None,
        line_id: str | None = None,
    ) -> ContinuationResolution:
        ensure_company_mode_active(mode, expected_line_id=line_id)
        if not mode.continue_existing_company_task:
            raise FoundationRuleError(
                "continuation resolution requires continue_existing_company_task=true"
            )
        resolution = resolve_continuation(
            self.registry,
            ContinuationRequest(
                request_id=request_id,
                reason=reason,
                company_task_id=company_task_id_value,
                task_id=task_id_value,
                line_id=line_id,
            ),
        )
        if resolution.needs_confirmation:
            return resolution
        if mode.target_line_id and resolution.line_id and mode.target_line_id != resolution.line_id:
            raise FoundationRuleError(
                f"continuation resolved to line {resolution.line_id}, but mode gate expected {mode.target_line_id}"
            )
        if resolution.resume_task_id:
            board = self.board(resolution.line_id)
            board.append_event(
                resolution.resume_task_id,
                {
                    "kind": "continuation_resolved",
                    "payload": {
                        "request_id": resolution.request_id,
                        "company_task_id": resolution.company_task_id,
                        "line_id": resolution.line_id,
                        "current_task_id": resolution.current_task_id,
                        "resume_task_id": resolution.resume_task_id,
                        "last_updated_task_id": resolution.last_updated_task_id,
                        "owner_role_id": resolution.owner_role_id,
                        "status": resolution.status,
                        "active_task_ids": list(resolution.active_task_ids),
                        "reason": resolution.reason,
                    },
                },
            )
        return resolution

    def assign_specialist_task(
        self,
        *,
        request_id: str,
        line_id: str,
        parent_task_id_value: str,
        task_local_id: str,
        assigned_to: str,
        task_type: str,
        allowed_actions: Sequence[str],
        reason: str,
        requested_by: str = "line-orchestrator",
        assigned_by: str | None = None,
    ) -> TaskRecord:
        line = self.require_line(line_id)
        board = self.board(line_id)
        parent = board.load_task(parent_task_id_value)
        ensure_company_task_context(parent)
        assigner = assigned_by or line.orchestrator_role_id
        if assigned_to not in line.allowed_role_ids:
            raise FoundationRuleError(f"specialist role not allowed in line: {assigned_to}")
        ensure_task_matches_declared_class(
            line=line,
            task_type=task_type,
            assigned_to=assigned_to,
            allowed_actions=allowed_actions,
        )
        task = TaskRecord(
            task_id=task_id(line_id, task_local_id),
            company_task_id=parent.company_task_id,
            request_id=request_id,
            line_id=line_id,
            requested_by=requested_by,
            assigned_by=assigner,
            assigned_to=assigned_to,
            task_type=task_type,
            state=TaskState.INBOX,
            allowed_actions=list(allowed_actions),
            artifact_root=line.artifact_root,
            artifact_paths=[],
            parent_task_id=parent.task_id,
            session_mode=parent.session_mode,
            activation_reason=parent.activation_reason,
            activation_scope=parent.activation_scope,
        )
        ensure_child_task_inherits_company_context(parent, task)
        ensure_task_assignment_is_legal(task, line.allowed_role_ids)
        board.create_task(task, note=reason)
        updated = board.transition(task.task_id, TaskState.ASSIGNED, note=f"assigned to specialist {assigned_to}")
        self.registry.register_child_task(updated)
        board.append_event(
            task.task_id,
            {
                "kind": "specialist_task_assigned",
                "company_task_id": updated.company_task_id,
                "parent_task_id": updated.parent_task_id,
                "assigned_by": assigner,
                "assigned_to": assigned_to,
                "task_type": task_type,
                "allowed_actions": list(allowed_actions),
                "note": reason,
            },
        )
        return updated

    def register_spawned_session(
        self,
        *,
        line_id: str,
        task_id_value: str,
        session_key: str,
        role_id: str,
    ) -> TaskRecord:
        line = self.require_line(line_id)
        ensure_session_registration_allowed(line)
        board = self.board(line_id)
        task = board.load_task(task_id_value)
        if role_id != task.assigned_to:
            raise FoundationRuleError(
                f"spawned session role mismatch: {role_id} != assigned {task.assigned_to}"
            )
        self.registry.bind_spawned_session(task=task, session_key=session_key, role_id=role_id)
        board.append_event(
            task.task_id,
            {
                "kind": "spawned_session_registered",
                "session_key": session_key,
                "role_id": role_id,
            },
        )
        return task

    def request_meeting(
        self,
        *,
        mode: ModeDecision,
        request_id: str,
        line_id: str,
        task_id_value: str,
        meeting_local_id: str,
        topic: str,
        participant_role_ids: Sequence[str],
        agenda: Sequence[str],
        reason: str,
    ) -> MeetingDispatch:
        ensure_company_mode_active(mode, expected_line_id=line_id)
        line = self.require_line(line_id)
        ensure_meetings_enabled(line)
        board = self.board(line_id)
        meeting_board = self.meeting_board(line_id)
        task = board.load_task(task_id_value)
        cmd = self.dispatcher.request_line_meeting(
            request_id=request_id,
            line_id=line_id,
            task_id=task_id_value,
            meeting_id=f"meeting:{line_id}:{meeting_local_id}",
            reason=reason,
            activation_reason=mode.reason,
            activation_scope=mode.scope.value,
        )
        board.assert_control_tower_command_allowed(task, cmd)
        meeting = open_meeting(
            line,
            task=task,
            local_id=meeting_local_id,
            topic=topic,
            participant_role_ids=participant_role_ids,
            agenda=list(agenda),
        )
        meeting_board.create_meeting(meeting, note=reason)
        updated = board.transition(task.task_id, TaskState.MEETING, note=reason)
        self.registry.sync_task(
            updated,
            resume_task_id=updated.task_id,
            owner_role_id=line.meeting_moderator_role_id,
        )
        board.append_event(
            task.task_id,
            {
                "kind": "meeting_requested",
                "meeting_id": meeting.meeting_id,
                "payload": command_to_payload(cmd),
            },
        )
        return MeetingDispatch(command=command_to_payload(cmd), task=updated, meeting=meeting)

    def open_line_meeting(
        self,
        *,
        line_id: str,
        task_id_value: str,
        meeting_local_id: str,
        topic: str,
        participant_role_ids: Sequence[str],
        agenda: Sequence[str],
        reason: str,
        requested_by: str | None = None,
    ) -> MeetingDispatch:
        line = self.require_line(line_id)
        ensure_meetings_enabled(line)
        board = self.board(line_id)
        meeting_board = self.meeting_board(line_id)
        task = board.load_task(task_id_value)
        ensure_company_task_context(task)
        requester = requested_by or line.orchestrator_role_id
        if requester != line.orchestrator_role_id:
            raise FoundationRuleError(
                f"only the line orchestrator may open a line-local meeting: {requester}"
            )
        if task.assigned_to != line.orchestrator_role_id:
            raise FoundationRuleError(
                f"line meeting must attach to an orchestrator-owned task, got {task.assigned_to}"
            )
        meeting = open_meeting(
            line,
            task=task,
            local_id=meeting_local_id,
            topic=topic,
            participant_role_ids=participant_role_ids,
            agenda=list(agenda),
        )
        meeting_board.create_meeting(meeting, note=reason)
        updated = board.transition(task.task_id, TaskState.MEETING, note=reason)
        self.registry.sync_task(
            updated,
            resume_task_id=updated.task_id,
            owner_role_id=line.meeting_moderator_role_id,
        )
        board.append_event(
            task.task_id,
            {
                "kind": "line_meeting_requested",
                "requested_by": requester,
                "meeting_id": meeting.meeting_id,
                "topic": topic,
                "agenda": list(agenda),
                "participant_role_ids": list(participant_role_ids),
                "reason": reason,
            },
        )
        return MeetingDispatch(command={}, task=updated, meeting=meeting)

    def record_meeting_outcome(
        self,
        *,
        line_id: str,
        meeting_id_value: str,
        decision_summary: str,
        next_actions: Sequence[str],
        unresolved_risks: Sequence[str],
        final_status: str,
        requested_by: str | None = None,
    ) -> MeetingOutcomeResult:
        if final_status not in {"converged", "blocked"}:
            raise FoundationRuleError(
                f"meeting outcome must be converged or blocked, got {final_status}"
            )
        line = self.require_line(line_id)
        board = self.board(line_id)
        meeting_board = self.meeting_board(line_id)
        requester = requested_by or line.meeting_moderator_role_id
        if requester not in {line.meeting_moderator_role_id, line.orchestrator_role_id}:
            raise FoundationRuleError(
                f"invalid meeting outcome requester for line {line_id}: {requester}"
            )
        meeting = meeting_board.load_meeting(meeting_id_value)
        if meeting.status == "opened":
            meeting = meeting_board.transition(meeting.meeting_id, "running", note="meeting started")
        meeting = meeting_board.record_minutes(
            meeting.meeting_id,
            decision_summary=decision_summary,
            next_actions=next_actions,
            unresolved_risks=unresolved_risks,
            status=final_status,
            note="meeting outcome recorded",
        )
        task = board.load_task(meeting.task_id)
        if task.state != TaskState.MEETING:
            raise FoundationRuleError(
                f"meeting outcome requires task in meeting state, got {task.state.value}"
            )
        target_state = TaskState.IN_PROGRESS if final_status == "converged" else TaskState.BLOCKED
        updated = board.transition(task.task_id, target_state, note=decision_summary)
        self.registry.sync_task(
            updated,
            resume_task_id=updated.task_id,
            owner_role_id=line.orchestrator_role_id,
        )
        board.append_event(
            updated.task_id,
            {
                "kind": "meeting_outcome_applied",
                "meeting_id": meeting.meeting_id,
                "final_status": final_status,
                "decision_summary": decision_summary,
                "next_actions": list(next_actions),
                "unresolved_risks": list(unresolved_risks),
                "requested_by": requester,
            },
        )
        return MeetingOutcomeResult(task=updated, meeting=meeting)

    def close_task(
        self,
        *,
        mode: ModeDecision,
        request_id: str,
        line_id: str,
        task_id_value: str,
        reason: str,
        fail: bool = False,
    ) -> TaskRecord:
        ensure_company_mode_active(mode, expected_line_id=line_id)
        line = self.require_line(line_id)
        board = self.board(line_id)
        task = board.load_task(task_id_value)
        if not fail:
            ensure_close_allowed_by_review_policy(line, task)
        cmd = self.dispatcher.close_task(
            request_id=request_id,
            line_id=line_id,
            task_id=task_id_value,
            reason=reason,
            status_note="failed" if fail else "done",
            activation_reason=mode.reason,
            activation_scope=mode.scope.value,
        )
        board.assert_control_tower_command_allowed(task, cmd)
        target = TaskState.FAILED if fail else TaskState.DONE
        updated = board.transition(task.task_id, target, note=reason)
        self.registry.sync_task(updated, resume_task_id=updated.task_id, owner_role_id=updated.assigned_to)
        board.append_event(
            task.task_id,
            {
                "kind": "control_tower_command",
                "payload": command_to_payload(cmd),
            },
        )
        return updated

    def ingest_worker_completion(
        self,
        *,
        line_id: str,
        task_id_value: str,
        payload: str | Mapping[str, object],
        reserved_role_ids: Sequence[str] | None = None,
        source_session_key: str | None = None,
        source_role_id: str | None = None,
    ) -> tuple[ComplianceReport, TaskRecord | None]:
        line = self.require_line(line_id)
        board = self.board(line_id)
        task = board.load_task(task_id_value)
        report = audit_post_run_payload(
            payload,
            task=task,
            line=line,
            reserved_role_ids=reserved_role_ids,
        )
        result = None
        has_registered_sessions = self.registry.has_any_bound_session_for_task(task)
        if report.ok:
            result = coerce_worker_result(payload)
            if source_role_id is not None and source_role_id != result.role_id:
                report.add_issue(
                    "worker.source_role_mismatch",
                    f"completion source role mismatch: {source_role_id} != payload role {result.role_id}",
                )
            if source_role_id is not None and source_role_id != task.assigned_to:
                report.add_issue(
                    "worker.source_assignee_mismatch",
                    f"completion source role mismatch: {source_role_id} != assigned {task.assigned_to}",
                )
            if has_registered_sessions and source_session_key is None:
                report.add_issue(
                    "worker.missing_source_session_key",
                    f"task {task.task_id} has registered spawned sessions, but completion source_session_key is missing",
                )
            if source_session_key is not None:
                if source_role_id is None:
                    report.add_issue(
                        "worker.missing_source_role_id",
                        "completion source_session_key requires source_role_id",
                    )
                elif not self.registry.has_bound_session(
                    task=task,
                    session_key=source_session_key,
                    role_id=source_role_id,
                ):
                    report.add_issue(
                        "worker.unregistered_source_session",
                        f"completion source session is not registered for task {task.task_id}: {source_session_key} / {source_role_id}",
                    )
        board.append_event(
            task.task_id,
            {
                "kind": "worker_completion_audit",
                "ok": report.ok,
                "issues": [issue.__dict__ for issue in report.issues],
                "notes": report.notes,
                "source_session_key": source_session_key,
                "source_role_id": source_role_id,
            },
        )
        if not report.ok or result is None:
            return report, None

        current = board.load_task(task.task_id)
        if current.state == TaskState.ASSIGNED:
            current = board.transition(current.task_id, TaskState.IN_PROGRESS, note="worker completion implies work started")

        current = board.update_artifacts(current.task_id, result.artifact_paths, note="artifacts accepted from worker")
        next_state = self._next_state_from_worker_result(line, current, result)
        if next_state != current.state:
            current = board.transition(current.task_id, next_state, note=result.summary)
        self.registry.sync_task(current)
        self.registry.record_completion_source(
            task=current,
            session_key=source_session_key,
            role_id=source_role_id,
            status=result.status,
            summary=result.summary,
            next_step=result.next_step,
        )

        resume_task_id = current.task_id
        owner_role_id = current.assigned_to
        if current.parent_task_id and result.status in {"complete", "blocked", "needs_review", "needs_meeting"}:
            parent = board.load_task(current.parent_task_id)
            resume_task_id = parent.task_id
            owner_role_id = parent.assigned_to
        self.registry.set_resume_target(
            task=current,
            resume_task_id=resume_task_id,
            owner_role_id=owner_role_id,
        )

        board.append_event(
            current.task_id,
            {
                "kind": "worker_completion_accepted",
                "role_id": result.role_id,
                "status": result.status,
                "summary": result.summary,
                "next_step": result.next_step,
                "artifact_paths": [str(path) for path in result.artifact_paths],
                "source_session_key": source_session_key,
                "source_role_id": source_role_id,
                "resume_task_id": resume_task_id,
                "resume_owner_role_id": owner_role_id,
            },
        )
        return report, current

    @staticmethod
    def _next_state_from_worker_result(line: BusinessLine, task: TaskRecord, result) -> TaskState:
        if result.status == "blocked":
            return TaskState.BLOCKED
        if result.status == "needs_meeting":
            return TaskState.MEETING
        if result.status == "needs_review":
            return TaskState.REVIEW
        if result.status == "complete":
            if task_requires_review(line, task):
                return TaskState.REVIEW
            return TaskState.DONE
        return TaskState.IN_PROGRESS
