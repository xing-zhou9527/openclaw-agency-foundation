from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from .guardrails import FoundationRuleError, ensure_meeting_is_same_line
from .models import BusinessLine, MeetingRecord, TaskRecord
from .router import meeting_id


def build_minutes_path(line: BusinessLine, local_id: str) -> Path:
    return line.meeting_root / local_id / "minutes.md"


def open_meeting(
    line: BusinessLine,
    task: TaskRecord,
    local_id: str,
    topic: str,
    participant_role_ids: Iterable[str],
    agenda: List[str],
    round_limit: int | None = None,
) -> MeetingRecord:
    participants = list(dict.fromkeys(participant_role_ids))
    round_limit = line.meeting_policy.default_round_limit if round_limit is None else round_limit
    if len(participants) < 2:
        raise FoundationRuleError("meeting requires at least 2 unique participants")
    if not topic.strip():
        raise FoundationRuleError("meeting requires a non-empty topic")
    if not agenda or not all(item.strip() for item in agenda):
        raise FoundationRuleError("meeting requires a non-empty agenda")
    if round_limit < 1 or round_limit > 10:
        raise FoundationRuleError("meeting round_limit must be between 1 and 10")

    record = MeetingRecord(
        meeting_id=meeting_id(line.line_id, local_id),
        company_task_id=task.company_task_id,
        task_id=task.task_id,
        line_id=line.line_id,
        topic=topic,
        moderator_role_id=line.meeting_moderator_role_id,
        participant_role_ids=participants,
        agenda=agenda,
        round_limit=round_limit,
        minutes_path=build_minutes_path(line, local_id),
    )
    ensure_meeting_is_same_line(record, line)
    return record
