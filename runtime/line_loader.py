from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

from .guardrails import FoundationRuleError
from .models import BusinessLine
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


def business_line_from_manifest_payload(payload: Mapping[str, object], *, lines_root: Path) -> BusinessLine:
    required = {
        "line_id",
        "objective",
        "orchestrator_role_id",
        "meeting_moderator_role_id",
        "specialists",
        "task_classes",
        "review_policy",
        "meetings",
        "sessions",
    }
    missing = [key for key in required if key not in payload]
    if missing:
        raise FoundationRuleError(
            f"business-line manifest missing required fields: {', '.join(sorted(missing))}"
        )

    line_id = str(payload["line_id"])
    if not line_id.strip():
        raise FoundationRuleError("business-line manifest line_id cannot be empty")

    orchestrator_role_id = str(payload["orchestrator_role_id"]).strip()
    meeting_moderator_role_id = str(payload["meeting_moderator_role_id"]).strip()
    if not orchestrator_role_id:
        raise FoundationRuleError(
            f"business-line manifest orchestrator_role_id cannot be empty: {line_id}"
        )
    if not meeting_moderator_role_id:
        raise FoundationRuleError(
            f"business-line manifest meeting_moderator_role_id cannot be empty: {line_id}"
        )

    specialists_raw = payload.get("specialists")
    if not isinstance(specialists_raw, list) or not specialists_raw:
        raise FoundationRuleError(
            f"business-line manifest specialists must be a non-empty list: {line_id}"
        )

    specialist_role_ids: list[str] = []
    for item in specialists_raw:
        if not isinstance(item, dict):
            raise FoundationRuleError(
                f"business-line manifest specialist entry must be an object: {line_id}"
            )
        role_id = str(item.get("role_id", "")).strip()
        if not role_id:
            raise FoundationRuleError(
                f"business-line manifest specialist is missing role_id: {line_id}"
            )
        specialist_role_ids.append(role_id)

    if len(set(specialist_role_ids)) != len(specialist_role_ids):
        raise FoundationRuleError(
            f"business-line manifest specialist role_ids must be unique: {line_id}"
        )

    roots = build_line_roots(Path(lines_root), line_id)
    return BusinessLine(
        line_id=line_id,
        namespace=line_namespace(line_id),
        workspace_root=roots["workspace_root"],
        artifact_root=roots["artifact_root"],
        meeting_root=roots["meeting_root"],
        task_root=roots["task_root"],
        orchestrator_role_id=orchestrator_role_id,
        meeting_moderator_role_id=meeting_moderator_role_id,
        allowed_role_ids=specialist_role_ids,
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
