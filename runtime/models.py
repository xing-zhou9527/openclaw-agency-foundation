from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List


class ActorKind(str, Enum):
    CONTROL_TOWER = "control_tower"
    LINE_ORCHESTRATOR = "line_orchestrator"
    MEETING_MODERATOR = "meeting_moderator"
    SPECIALIST = "specialist"


class TaskState(str, Enum):
    INBOX = "inbox"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    MEETING = "meeting"
    REVIEW = "review"
    DONE = "done"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class SpecialistRoleSpec:
    role_id: str
    upstream_role: str
    purpose: str
    allowed_actions: List[str] = field(default_factory=list)
    primary_artifact_types: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class TaskClassSpec:
    task_type: str
    default_owner_role_id: str
    allowed_actions: List[str] = field(default_factory=list)
    requires_review: bool = False


@dataclass(frozen=True)
class ReviewPolicy:
    required: bool = False
    reviewer_role_ids: List[str] = field(default_factory=list)
    close_requires_review: bool = False


@dataclass(frozen=True)
class MeetingPolicy:
    enabled: bool = True
    same_line_only: bool = True
    default_round_limit: int = 3


@dataclass(frozen=True)
class SessionPolicy:
    spawn_strategy: str = "on_demand"
    register_spawned_sessions: bool = True


@dataclass(frozen=True)
class BusinessLine:
    line_id: str
    namespace: str
    workspace_root: Path
    artifact_root: Path
    meeting_root: Path
    task_root: Path
    orchestrator_role_id: str
    meeting_moderator_role_id: str
    allowed_role_ids: List[str] = field(default_factory=list)
    objective: str = ""
    scope_notes: List[str] = field(default_factory=list)
    specialists: Dict[str, SpecialistRoleSpec] = field(default_factory=dict)
    task_classes: Dict[str, TaskClassSpec] = field(default_factory=dict)
    review_policy: ReviewPolicy = field(default_factory=ReviewPolicy)
    meeting_policy: MeetingPolicy = field(default_factory=MeetingPolicy)
    session_policy: SessionPolicy = field(default_factory=SessionPolicy)
    cross_line_policy: str = "deny"


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    company_task_id: str
    request_id: str
    line_id: str
    requested_by: str
    assigned_by: str
    assigned_to: str
    task_type: str
    state: TaskState
    allowed_actions: List[str]
    artifact_root: Path
    artifact_paths: List[Path] = field(default_factory=list)
    parent_task_id: str | None = None
    session_mode: str = "company"
    activation_reason: str = ""
    activation_scope: str = "request"


@dataclass(frozen=True)
class MeetingRecord:
    meeting_id: str
    company_task_id: str
    task_id: str
    line_id: str
    topic: str
    moderator_role_id: str
    participant_role_ids: List[str]
    agenda: List[str]
    round_limit: int
    minutes_path: Path
    decision_summary: str = ""
    next_actions: List[str] = field(default_factory=list)
    unresolved_risks: List[str] = field(default_factory=list)
    status: str = "opened"
