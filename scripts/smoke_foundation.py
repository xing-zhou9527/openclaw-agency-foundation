#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path


def load_runtime_package(source_root: Path):
    work = Path(tempfile.mkdtemp(prefix="agency-foundation-smoke-"))
    pkg = work / "openclaw_agency_foundation"
    shutil.copytree(source_root, pkg)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "runtime" / "__init__.py").write_text("", encoding="utf-8")
    sys.path.insert(0, str(work))
    return work


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    temp_root = load_runtime_package(repo)

    from openclaw_agency_foundation.runtime.engine import FoundationEngine
    from openclaw_agency_foundation.runtime.hooks import SubagentCompletionEvent, SubagentCompletionHook
    from openclaw_agency_foundation.runtime.mode_gate import (
        ActivationScope,
        ModeIntent,
        RequestKind,
        coerce_mode_decision,
        decide_session_mode,
        mode_decision_to_payload,
    )
    from openclaw_agency_foundation.runtime.guardrails import FoundationRuleError

    engine = FoundationEngine.from_line_ids(base_dir=temp_root / "runtime-state", line_ids=["marketing"])
    engine.lines["marketing"] = engine.lines["marketing"].__class__(
        **{
            **engine.lines["marketing"].__dict__,
            "allowed_role_ids": ["marketing-writer", "marketing-reviewer"],
        }
    )
    engine.taskboards["marketing"] = engine.taskboards["marketing"].__class__(engine.lines["marketing"].task_root)
    engine.meetingboards["marketing"] = engine.meetingboards["marketing"].__class__(engine.lines["marketing"].meeting_root)
    engine.dispatcher = engine.dispatcher.__class__(engine.lines)

    assistant_mode = decide_session_mode(
        ModeIntent(
            request_id="req-meta",
            request_kind=RequestKind.META_FOUNDATION,
            reason="discussing the foundation itself",
        )
    )
    assistant_payload = mode_decision_to_payload(assistant_mode)
    assistant_roundtrip = coerce_mode_decision(assistant_payload)

    try:
        engine.route_request(
            mode=assistant_roundtrip,
            request_id="req-meta",
            line_id="marketing",
            task_local_id="001",
            reason="assistant mode must not route",
        )
        raise AssertionError("assistant mode should not be able to route company work")
    except FoundationRuleError:
        pass

    company_mode = decide_session_mode(
        ModeIntent(
            request_id="req-ops",
            request_kind=RequestKind.COMPANY_OPERATION,
            reason="user asked to actually operate the marketing workflow",
            requires_business_execution=True,
            requires_line_ownership=True,
            target_line_id="marketing",
            scope=ActivationScope.REQUEST,
        )
    )

    root = engine.route_request(
        mode=company_mode,
        request_id="req-ops",
        line_id="marketing",
        task_local_id="001",
        reason="route company task into marketing",
    )
    child = engine.assign_specialist_task(
        request_id="req-ops",
        line_id="marketing",
        parent_task_id_value=root.task.task_id,
        task_local_id="002",
        assigned_to="marketing-writer",
        task_type="build",
        allowed_actions=["produce_artifact", "review_artifact", "request_meeting"],
        reason="assign content draft",
    )
    engine.register_spawned_session(
        line_id="marketing",
        task_id_value=child.task_id,
        session_key="sess-123",
        role_id="marketing-writer",
    )

    hook = SubagentCompletionHook(engine)
    bad = hook.handle(
        SubagentCompletionEvent(
            line_id="marketing",
            task_id=child.task_id,
            source_session_key="sess-bad",
            source_role_id="marketing-writer",
            payload={
                "task_id": child.task_id,
                "line_id": "marketing",
                "role_id": "marketing-writer",
                "status": "complete",
                "summary": "draft completed",
                "next_step": "review artifact",
                "artifact_paths": [str(engine.lines["marketing"].artifact_root / "draft.md")],
                "risks": [],
            },
        )
    )
    assert bad.report.ok is False

    result = hook.handle(
        SubagentCompletionEvent(
            line_id="marketing",
            task_id=child.task_id,
            source_session_key="sess-123",
            source_role_id="marketing-writer",
            payload={
                "task_id": child.task_id,
                "line_id": "marketing",
                "role_id": "marketing-writer",
                "status": "complete",
                "summary": "draft completed",
                "next_step": "review artifact",
                "artifact_paths": [str(engine.lines["marketing"].artifact_root / "draft.md")],
                "risks": [],
            },
        )
    )
    assert result.report.ok is True

    entry = engine.registry.company_task_for_task(child.task_id)
    assert entry.company_task_id == root.task.company_task_id
    assert entry.current_task_id == child.task_id
    assert entry.resume_task_id == root.task.task_id
    assert entry.last_updated_task_id == child.task_id
    assert any(b.session_key == "sess-123" for b in entry.spawned_sessions)

    meeting = engine.open_line_meeting(
        line_id="marketing",
        task_id_value=root.task.task_id,
        meeting_local_id="001",
        topic="Resolve positioning disagreement",
        participant_role_ids=["marketing-writer", "marketing-reviewer"],
        agenda=["Align message", "Choose next action"],
        reason="same-line coordination needed",
    )
    assert meeting.meeting.line_id == "marketing"
    outcome = engine.record_meeting_outcome(
        line_id="marketing",
        meeting_id_value=meeting.meeting.meeting_id,
        decision_summary="Use positioning A",
        next_actions=["marketing-orchestrator assigns review", "marketing-reviewer reviews draft"],
        unresolved_risks=["headline may still be weak"],
        final_status="converged",
    )
    assert outcome.task.state.value == "in_progress"
    assert outcome.meeting.status == "converged"
    assert outcome.meeting.minutes_path.exists()

    continuation_mode = decide_session_mode(
        ModeIntent(
            request_id="req-continue",
            request_kind=RequestKind.COMPANY_OPERATION,
            reason="continue existing marketing task",
            continue_existing_company_task=True,
            target_line_id="marketing",
            scope=ActivationScope.STICKY_TASK,
        )
    )
    cont = engine.resolve_continuation(
        mode=continuation_mode,
        request_id="req-continue",
        reason="continue existing marketing task",
        company_task_id_value=root.task.company_task_id,
        line_id="marketing",
    )
    assert cont.company_task_id == root.task.company_task_id
    assert cont.resume_task_id == root.task.task_id
    assert cont.owner_role_id == "marketing-orchestrator"

    print("smoke_foundation_ok")


if __name__ == "__main__":
    main()
