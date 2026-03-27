from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .guardrails import FoundationRuleError
from .manifest_validation import validate_business_line_manifest_payload
from .models import (
    BusinessLine,
    MeetingPolicy,
    ReviewPolicy,
    SessionPolicy,
    SpecialistRoleSpec,
    TaskClassSpec,
)
from .router import build_line_roots, line_namespace


def line_manifest_path(manifest_root: Path, line_id: str) -> Path:
    return Path(manifest_root) / line_id / "manifest.json"


def load_manifest_payload(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise FoundationRuleError(f"business-line manifest not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FoundationRuleError(f"invalid business-line manifest json: {path}") from exc
    if not isinstance(payload, dict):
        raise FoundationRuleError(f"business-line manifest must be an object: {path}")
    return payload


def business_line_from_manifest_payload(payload: object, *, lines_root: Path) -> BusinessLine:
    normalized = validate_business_line_manifest_payload(payload)
    line_id = normalized["line_id"]
    roots = build_line_roots(Path(lines_root), line_id)

    specialists = {
        item["role_id"]: SpecialistRoleSpec(
            role_id=item["role_id"],
            upstream_role=item["upstream_role"],
            purpose=item["purpose"],
            allowed_actions=list(item["allowed_actions"]),
            primary_artifact_types=list(item["primary_artifact_types"]),
        )
        for item in normalized["specialists"]
    }
    task_classes = {
        item["task_type"]: TaskClassSpec(
            task_type=item["task_type"],
            default_owner_role_id=item["default_owner_role_id"],
            allowed_actions=list(item["allowed_actions"]),
            requires_review=bool(item["requires_review"]),
        )
        for item in normalized["task_classes"]
    }
    review_policy = ReviewPolicy(
        required=bool(normalized["review_policy"]["required"]),
        reviewer_role_ids=list(normalized["review_policy"]["reviewer_role_ids"]),
        close_requires_review=bool(normalized["review_policy"]["close_requires_review"]),
    )
    meeting_policy = MeetingPolicy(
        enabled=bool(normalized["meetings"]["enabled"]),
        same_line_only=bool(normalized["meetings"]["same_line_only"]),
        default_round_limit=int(normalized["meetings"]["default_round_limit"]),
    )
    session_policy = SessionPolicy(
        spawn_strategy=str(normalized["sessions"]["spawn_strategy"]),
        register_spawned_sessions=bool(normalized["sessions"]["register_spawned_sessions"]),
    )

    return BusinessLine(
        line_id=line_id,
        namespace=line_namespace(line_id),
        workspace_root=roots["workspace_root"],
        artifact_root=roots["artifact_root"],
        meeting_root=roots["meeting_root"],
        task_root=roots["task_root"],
        orchestrator_role_id=normalized["orchestrator_role_id"],
        meeting_moderator_role_id=normalized["meeting_moderator_role_id"],
        allowed_role_ids=list(specialists.keys()),
        objective=normalized["objective"],
        scope_notes=list(normalized["scope_notes"]),
        specialists=specialists,
        task_classes=task_classes,
        review_policy=review_policy,
        meeting_policy=meeting_policy,
        session_policy=session_policy,
    )


def load_business_line_from_manifest_path(manifest_path: Path, *, lines_root: Path) -> BusinessLine:
    payload = load_manifest_payload(Path(manifest_path))
    return business_line_from_manifest_payload(payload, lines_root=Path(lines_root))


def load_business_lines_from_manifest_root(
    manifest_root: Path,
    *,
    lines_root: Path,
    line_ids: Iterable[str] | None = None,
) -> dict[str, BusinessLine]:
    manifest_root = Path(manifest_root)
    if not manifest_root.exists():
        raise FoundationRuleError(
            f"business-line manifest root does not exist: {manifest_root}"
        )
    ids = list(line_ids) if line_ids is not None else sorted(
        path.name for path in manifest_root.iterdir() if path.is_dir() and (path / "manifest.json").exists()
    )
    if not ids:
        raise FoundationRuleError(
            f"no business-line manifests found under: {manifest_root}"
        )
    loaded: dict[str, BusinessLine] = {}
    for line_id in ids:
        manifest_path = line_manifest_path(manifest_root, line_id)
        loaded[line_id] = load_business_line_from_manifest_path(
            manifest_path,
            lines_root=Path(lines_root),
        )
    return loaded
