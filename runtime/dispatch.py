from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Mapping

from .guardrails import FoundationRuleError
from .models import BusinessLine
from .mode_gate import ActivationScope
from .policy import ControlTowerCommand, validate_control_tower_command


class ControlTowerDispatcher:
    """Fail-closed wrapper for main-session control-tower actions.

    The main controller session should never emit raw free-form routing actions.
    It must go through this wrapper so every command is normalized and validated
    before it becomes executable intent.
    """

    def __init__(self, lines: Mapping[str, BusinessLine]):
        self._lines: Dict[str, BusinessLine] = dict(lines)

    def require_line(self, line_id: str) -> BusinessLine:
        line = self._lines.get(line_id)
        if line is None:
            raise FoundationRuleError(f"unknown business line: {line_id}")
        return line

    def emit(self, cmd: ControlTowerCommand) -> ControlTowerCommand:
        self.require_line(cmd.line_id)
        validate_control_tower_command(cmd)
        return cmd

    def dispatch_line(
        self,
        *,
        request_id: str,
        line_id: str,
        reason: str,
        activation_reason: str,
        activation_scope: str = ActivationScope.REQUEST.value,
        task_id: str | None = None,
        next_owner: str | None = None,
        status_note: str | None = None,
    ) -> ControlTowerCommand:
        self.require_line(line_id)
        line = self._lines[line_id]
        owner = next_owner or line.orchestrator_role_id
        return self.emit(
            ControlTowerCommand(
                request_id=request_id,
                command="dispatch_line",
                line_id=line_id,
                reason=reason,
                task_id=task_id,
                next_owner=owner,
                status_note=status_note,
                activation_reason=activation_reason,
                activation_scope=activation_scope,
            )
        )

    def request_line_meeting(
        self,
        *,
        request_id: str,
        line_id: str,
        reason: str,
        activation_reason: str,
        activation_scope: str = ActivationScope.REQUEST.value,
        meeting_id: str,
        task_id: str | None = None,
        status_note: str | None = None,
    ) -> ControlTowerCommand:
        self.require_line(line_id)
        return self.emit(
            ControlTowerCommand(
                request_id=request_id,
                command="request_line_meeting",
                line_id=line_id,
                reason=reason,
                task_id=task_id,
                meeting_id=meeting_id,
                status_note=status_note,
                activation_reason=activation_reason,
                activation_scope=activation_scope,
            )
        )

    def query_line_status(
        self,
        *,
        request_id: str,
        line_id: str,
        reason: str,
        activation_reason: str,
        activation_scope: str = ActivationScope.REQUEST.value,
        task_id: str | None = None,
    ) -> ControlTowerCommand:
        self.require_line(line_id)
        return self.emit(
            ControlTowerCommand(
                request_id=request_id,
                command="query_line_status",
                line_id=line_id,
                reason=reason,
                task_id=task_id,
                activation_reason=activation_reason,
                activation_scope=activation_scope,
            )
        )

    def close_task(
        self,
        *,
        request_id: str,
        line_id: str,
        reason: str,
        activation_reason: str,
        activation_scope: str = ActivationScope.REQUEST.value,
        task_id: str,
        status_note: str | None = None,
    ) -> ControlTowerCommand:
        self.require_line(line_id)
        return self.emit(
            ControlTowerCommand(
                request_id=request_id,
                command="close_task",
                line_id=line_id,
                reason=reason,
                task_id=task_id,
                status_note=status_note,
                activation_reason=activation_reason,
                activation_scope=activation_scope,
            )
        )

    def escalate(
        self,
        *,
        request_id: str,
        line_id: str,
        reason: str,
        activation_reason: str,
        activation_scope: str = ActivationScope.REQUEST.value,
        task_id: str | None = None,
        status_note: str | None = None,
    ) -> ControlTowerCommand:
        self.require_line(line_id)
        return self.emit(
            ControlTowerCommand(
                request_id=request_id,
                command="escalate",
                line_id=line_id,
                reason=reason,
                task_id=task_id,
                status_note=status_note,
                activation_reason=activation_reason,
                activation_scope=activation_scope,
            )
        )


def command_to_payload(cmd: ControlTowerCommand) -> dict:
    return asdict(cmd)
