from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .audit import ComplianceReport
from .engine import FoundationEngine
from .models import TaskRecord


@dataclass(frozen=True)
class SubagentCompletionEvent:
    line_id: str
    task_id: str
    payload: str | Mapping[str, object]
    source_session_key: str | None = None
    source_role_id: str | None = None


@dataclass(frozen=True)
class HookResult:
    report: ComplianceReport
    task: TaskRecord | None


class SubagentCompletionHook:
    """Audit-first adapter for future OpenClaw completion integration.

    Any subagent completion path should flow through this hook so the payload is
    validated before the task board accepts it as line output.
    """

    def __init__(self, engine: FoundationEngine):
        self.engine = engine

    def handle(
        self,
        event: SubagentCompletionEvent,
        *,
        reserved_role_ids: Sequence[str] | None = None,
    ) -> HookResult:
        report, task = self.engine.ingest_worker_completion(
            line_id=event.line_id,
            task_id_value=event.task_id,
            payload=event.payload,
            reserved_role_ids=reserved_role_ids,
            source_session_key=event.source_session_key,
            source_role_id=event.source_role_id,
        )
        return HookResult(report=report, task=task)
