from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .guardrails import FoundationRuleError
from .models import MeetingRecord


ALLOWED_MEETING_TRANSITIONS: dict[str, set[str]] = {
    "opened": {"running", "converged", "blocked", "closed"},
    "running": {"converged", "blocked", "closed"},
    "converged": {"closed"},
    "blocked": {"closed"},
    "closed": set(),
}


def serialize_meeting(meeting: MeetingRecord) -> dict:
    payload = asdict(meeting)
    payload["minutes_path"] = str(meeting.minutes_path)
    return payload


def deserialize_meeting(payload: dict) -> MeetingRecord:
    return MeetingRecord(
        meeting_id=str(payload["meeting_id"]),
        company_task_id=str(payload["company_task_id"]),
        task_id=str(payload["task_id"]),
        line_id=str(payload["line_id"]),
        topic=str(payload["topic"]),
        moderator_role_id=str(payload["moderator_role_id"]),
        participant_role_ids=list(payload.get("participant_role_ids", [])),
        agenda=list(payload.get("agenda", [])),
        round_limit=int(payload.get("round_limit", 3)),
        minutes_path=Path(payload["minutes_path"]),
        decision_summary=str(payload.get("decision_summary", "")),
        next_actions=list(payload.get("next_actions", [])),
        unresolved_risks=list(payload.get("unresolved_risks", [])),
        status=str(payload.get("status", "opened")),
    )


class LineMeetingBoard:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _meeting_dir(self, meeting_id: str) -> Path:
        safe = meeting_id.replace(":", "__")
        return self.root / safe

    def _meeting_file(self, meeting_id: str) -> Path:
        return self._meeting_dir(meeting_id) / "meeting.json"

    def _events_file(self, meeting_id: str) -> Path:
        return self._meeting_dir(meeting_id) / "events.jsonl"

    def save_meeting(self, meeting: MeetingRecord) -> None:
        meeting_dir = self._meeting_dir(meeting.meeting_id)
        meeting_dir.mkdir(parents=True, exist_ok=True)
        self._meeting_file(meeting.meeting_id).write_text(
            json.dumps(serialize_meeting(meeting), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_meeting(self, meeting_id: str) -> MeetingRecord:
        path = self._meeting_file(meeting_id)
        if not path.exists():
            raise FoundationRuleError(f"meeting not found: {meeting_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return deserialize_meeting(payload)

    def append_event(self, meeting_id: str, event: dict) -> None:
        meeting_dir = self._meeting_dir(meeting_id)
        meeting_dir.mkdir(parents=True, exist_ok=True)
        with self._events_file(meeting_id).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    def create_meeting(self, meeting: MeetingRecord, note: str | None = None) -> MeetingRecord:
        if self._meeting_file(meeting.meeting_id).exists():
            raise FoundationRuleError(f"meeting already exists: {meeting.meeting_id}")
        self.save_meeting(meeting)
        self.append_event(
            meeting.meeting_id,
            {
                "kind": "meeting_created",
                "meeting_id": meeting.meeting_id,
                "company_task_id": meeting.company_task_id,
                "task_id": meeting.task_id,
                "status": meeting.status,
                "note": note or "",
            },
        )
        return meeting

    def transition(self, meeting_id: str, new_status: str, note: str = "") -> MeetingRecord:
        meeting = self.load_meeting(meeting_id)
        allowed = ALLOWED_MEETING_TRANSITIONS.get(meeting.status, set())
        if new_status not in allowed:
            raise FoundationRuleError(
                f"illegal meeting transition: {meeting.status} -> {new_status}"
            )
        updated = MeetingRecord(
            meeting_id=meeting.meeting_id,
            company_task_id=meeting.company_task_id,
            task_id=meeting.task_id,
            line_id=meeting.line_id,
            topic=meeting.topic,
            moderator_role_id=meeting.moderator_role_id,
            participant_role_ids=meeting.participant_role_ids,
            agenda=meeting.agenda,
            round_limit=meeting.round_limit,
            minutes_path=meeting.minutes_path,
            decision_summary=meeting.decision_summary,
            next_actions=meeting.next_actions,
            unresolved_risks=meeting.unresolved_risks,
            status=new_status,
        )
        self.save_meeting(updated)
        self.append_event(
            meeting_id,
            {
                "kind": "meeting_transition",
                "from": meeting.status,
                "to": new_status,
                "note": note,
            },
        )
        return updated

    def record_minutes(
        self,
        meeting_id: str,
        *,
        decision_summary: str,
        next_actions: Iterable[str],
        unresolved_risks: Iterable[str],
        status: str,
        note: str = "",
    ) -> MeetingRecord:
        meeting = self.load_meeting(meeting_id)
        actions = [item for item in next_actions]
        risks = [item for item in unresolved_risks]
        updated = MeetingRecord(
            meeting_id=meeting.meeting_id,
            company_task_id=meeting.company_task_id,
            task_id=meeting.task_id,
            line_id=meeting.line_id,
            topic=meeting.topic,
            moderator_role_id=meeting.moderator_role_id,
            participant_role_ids=meeting.participant_role_ids,
            agenda=meeting.agenda,
            round_limit=meeting.round_limit,
            minutes_path=meeting.minutes_path,
            decision_summary=decision_summary,
            next_actions=actions,
            unresolved_risks=risks,
            status=status,
        )
        updated.minutes_path.parent.mkdir(parents=True, exist_ok=True)
        updated.minutes_path.write_text(
            self._render_minutes(updated),
            encoding="utf-8",
        )
        self.save_meeting(updated)
        self.append_event(
            meeting_id,
            {
                "kind": "meeting_minutes_recorded",
                "decision_summary": decision_summary,
                "next_actions": actions,
                "unresolved_risks": risks,
                "status": status,
                "note": note,
            },
        )
        return updated

    @staticmethod
    def _render_minutes(meeting: MeetingRecord) -> str:
        participants = "\n".join(f"- {item}" for item in meeting.participant_role_ids)
        agenda = "\n".join(f"- {item}" for item in meeting.agenda)
        next_actions = "\n".join(f"- {item}" for item in meeting.next_actions) or "- none"
        unresolved_risks = "\n".join(f"- {item}" for item in meeting.unresolved_risks) or "- none"
        return (
            f"# Meeting Minutes\n\n"
            f"- meeting_id: `{meeting.meeting_id}`\n"
            f"- company_task_id: `{meeting.company_task_id}`\n"
            f"- task_id: `{meeting.task_id}`\n"
            f"- line_id: `{meeting.line_id}`\n"
            f"- moderator_role_id: `{meeting.moderator_role_id}`\n"
            f"- status: `{meeting.status}`\n\n"
            f"## Topic\n\n{meeting.topic}\n\n"
            f"## Participants\n\n{participants}\n\n"
            f"## Agenda\n\n{agenda}\n\n"
            f"## Decision Summary\n\n{meeting.decision_summary or 'No decision summary recorded.'}\n\n"
            f"## Next Actions\n\n{next_actions}\n\n"
            f"## Unresolved Risks\n\n{unresolved_risks}\n"
        )
