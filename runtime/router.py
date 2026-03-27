from __future__ import annotations

from pathlib import Path
from typing import Dict

from .guardrails import FoundationRuleError, ensure_control_tower_is_non_executing
from .models import ActorKind, BusinessLine


def company_task_id(line_id: str, local_id: str) -> str:
    return f"company:{line_id}:{local_id}"


def task_id(line_id: str, local_id: str) -> str:
    return f"task:{line_id}:{local_id}"


def meeting_id(line_id: str, local_id: str) -> str:
    return f"meeting:{line_id}:{local_id}"


def line_namespace(line_id: str) -> str:
    return f"line:{line_id}"


def build_line_roots(lines_root: Path, line_id: str) -> Dict[str, Path]:
    """Build line-local state roots under an external lines root.

    `lines_root` should normally resolve from the deployment/workdir layout
    (default `~/.gency/state/lines`) instead of the foundation code repo.
    """

    line_root = Path(lines_root) / line_id
    return {
        "line_root": line_root,
        "workspace_root": line_root / "workspace",
        "artifact_root": line_root / "artifacts",
        "meeting_root": line_root / "meetings",
        "task_root": line_root / "tasks",
    }


def build_line_template(lines_root: Path, line_id: str) -> BusinessLine:
    """Synthesize a line template from a lines root.

    This remains useful for smoke tests and transitional bootstrap flows, but it
    should be treated as a helper. Real line and role definitions are expected to
    come from external deployment assets, not from the foundation repo itself.
    """

    roots = build_line_roots(lines_root, line_id)
    return BusinessLine(
        line_id=line_id,
        namespace=line_namespace(line_id),
        workspace_root=roots["workspace_root"],
        artifact_root=roots["artifact_root"],
        meeting_root=roots["meeting_root"],
        task_root=roots["task_root"],
        orchestrator_role_id=f"{line_id}-orchestrator",
        meeting_moderator_role_id=f"{line_id}-meeting-moderator",
        allowed_role_ids=[],
    )


def assert_dispatch_allowed(actor_kind: ActorKind, action: str) -> None:
    if action == "produce_artifact":
        ensure_control_tower_is_non_executing(actor_kind)
    if actor_kind == ActorKind.CONTROL_TOWER and action not in {
        "dispatch",
        "request_meeting",
        "close_task",
        "escalate",
    }:
        raise FoundationRuleError(
            f"control tower cannot perform action: {action}"
        )
