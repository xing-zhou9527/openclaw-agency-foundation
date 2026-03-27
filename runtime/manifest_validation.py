from __future__ import annotations

import re
from typing import Any, Mapping

from .guardrails import FoundationRuleError


LINE_ID_RE = re.compile(r"^[a-z0-9-]+$")
ALLOWED_ACTIONS = {
    "produce_artifact",
    "review_artifact",
    "request_meeting",
    "escalate",
}
TASK_TYPES = {"research", "design", "build", "review", "ops", "meeting"}
SPAWN_STRATEGIES = {"on_demand", "persistent"}
CROSS_LINE_POLICIES = {"deny", "escalate_only"}


def _require_object(payload: Any, *, subject: str) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise FoundationRuleError(f"{subject} must be an object")
    return payload


def _reject_unknown_keys(payload: Mapping[str, object], allowed: set[str], *, subject: str) -> None:
    unknown = sorted(set(payload.keys()) - allowed)
    if unknown:
        raise FoundationRuleError(
            f"{subject} contains unknown fields: {', '.join(unknown)}"
        )


def _require_keys(payload: Mapping[str, object], required: set[str], *, subject: str) -> None:
    missing = sorted(key for key in required if key not in payload)
    if missing:
        raise FoundationRuleError(
            f"{subject} is missing required fields: {', '.join(missing)}"
        )


def _require_string(value: object, *, field_name: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise FoundationRuleError(f"{field_name} must be a string")
    if not allow_empty and not value.strip():
        raise FoundationRuleError(f"{field_name} cannot be empty")
    return value


def _require_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise FoundationRuleError(f"{field_name} must be a boolean")
    return value


def _require_int(value: object, *, field_name: str, min_value: int | None = None, max_value: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FoundationRuleError(f"{field_name} must be an integer")
    if min_value is not None and value < min_value:
        raise FoundationRuleError(f"{field_name} must be >= {min_value}")
    if max_value is not None and value > max_value:
        raise FoundationRuleError(f"{field_name} must be <= {max_value}")
    return value


def _require_string_list(value: object, *, field_name: str, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise FoundationRuleError(f"{field_name} must be an array")
    items: list[str] = []
    for index, item in enumerate(value):
        items.append(_require_string(item, field_name=f"{field_name}[{index}]"))
    if not allow_empty and not items:
        raise FoundationRuleError(f"{field_name} must not be empty")
    return items


def _require_unique_strings(values: list[str], *, field_name: str) -> None:
    if len(set(values)) != len(values):
        raise FoundationRuleError(f"{field_name} must contain unique strings")


def validate_deployment_manifest_payload(payload: object) -> dict:
    data = _require_object(payload, subject="deployment manifest")
    allowed = {
        "deployment_name",
        "home",
        "manifest_root",
        "prompt_root",
        "state_root",
        "lines_root",
        "registry_root",
        "enabled_lines",
        "line_manifest_files",
        "notes",
    }
    required = {"deployment_name", "enabled_lines"}
    _reject_unknown_keys(data, allowed, subject="deployment manifest")
    _require_keys(data, required, subject="deployment manifest")

    deployment_name = _require_string(data["deployment_name"], field_name="deployment_name")
    enabled_lines = _require_string_list(data["enabled_lines"], field_name="enabled_lines", allow_empty=False)
    _require_unique_strings(enabled_lines, field_name="enabled_lines")
    for line_id in enabled_lines:
        if not LINE_ID_RE.match(line_id):
            raise FoundationRuleError(f"enabled_lines contains invalid line_id: {line_id}")

    normalized = {
        "deployment_name": deployment_name,
        "enabled_lines": enabled_lines,
    }
    for key in {"home", "manifest_root", "prompt_root", "state_root", "lines_root", "registry_root"}:
        if key in data:
            normalized[key] = _require_string(data[key], field_name=key)

    line_manifest_files = data.get("line_manifest_files", {})
    if not isinstance(line_manifest_files, Mapping):
        raise FoundationRuleError("line_manifest_files must be an object")
    normalized_files: dict[str, str] = {}
    for line_id, path in line_manifest_files.items():
        if not isinstance(line_id, str) or not LINE_ID_RE.match(line_id):
            raise FoundationRuleError(f"line_manifest_files has invalid line_id key: {line_id}")
        normalized_files[line_id] = _require_string(path, field_name=f"line_manifest_files.{line_id}")
    unknown_manifest_keys = sorted(set(normalized_files.keys()) - set(enabled_lines))
    if unknown_manifest_keys:
        raise FoundationRuleError(
            f"line_manifest_files contains line_ids not present in enabled_lines: {', '.join(unknown_manifest_keys)}"
        )
    normalized["line_manifest_files"] = normalized_files

    notes = data.get("notes", [])
    normalized["notes"] = _require_string_list(notes, field_name="notes")
    return normalized


def validate_business_line_manifest_payload(payload: object) -> dict:
    data = _require_object(payload, subject="business-line manifest")
    allowed = {
        "line_id",
        "objective",
        "scope_notes",
        "orchestrator_role_id",
        "meeting_moderator_role_id",
        "specialists",
        "task_classes",
        "review_policy",
        "meetings",
        "sessions",
    }
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
    _reject_unknown_keys(data, allowed, subject="business-line manifest")
    _require_keys(data, required, subject="business-line manifest")

    line_id = _require_string(data["line_id"], field_name="line_id")
    if not LINE_ID_RE.match(line_id):
        raise FoundationRuleError(f"line_id is invalid: {line_id}")

    orchestrator_role_id = _require_string(data["orchestrator_role_id"], field_name="orchestrator_role_id")
    meeting_moderator_role_id = _require_string(data["meeting_moderator_role_id"], field_name="meeting_moderator_role_id")
    objective = _require_string(data["objective"], field_name="objective")
    scope_notes = _require_string_list(data.get("scope_notes", []), field_name="scope_notes")

    specialists_raw = data["specialists"]
    if not isinstance(specialists_raw, list) or not specialists_raw:
        raise FoundationRuleError("specialists must be a non-empty array")
    specialists: list[dict] = []
    specialist_role_ids: list[str] = []
    for index, item in enumerate(specialists_raw):
        spec = _require_object(item, subject=f"specialists[{index}]")
        allowed_spec_keys = {"role_id", "upstream_role", "purpose", "allowed_actions", "primary_artifact_types"}
        required_spec_keys = {"role_id", "upstream_role", "purpose", "allowed_actions"}
        _reject_unknown_keys(spec, allowed_spec_keys, subject=f"specialists[{index}]")
        _require_keys(spec, required_spec_keys, subject=f"specialists[{index}]")
        role_id = _require_string(spec["role_id"], field_name=f"specialists[{index}].role_id")
        upstream_role = _require_string(spec["upstream_role"], field_name=f"specialists[{index}].upstream_role")
        purpose = _require_string(spec["purpose"], field_name=f"specialists[{index}].purpose")
        allowed_actions = _require_string_list(spec["allowed_actions"], field_name=f"specialists[{index}].allowed_actions", allow_empty=False)
        _require_unique_strings(allowed_actions, field_name=f"specialists[{index}].allowed_actions")
        invalid_actions = sorted(set(allowed_actions) - ALLOWED_ACTIONS)
        if invalid_actions:
            raise FoundationRuleError(
                f"specialists[{index}].allowed_actions contains invalid actions: {', '.join(invalid_actions)}"
            )
        primary_artifact_types = _require_string_list(
            spec.get("primary_artifact_types", []),
            field_name=f"specialists[{index}].primary_artifact_types",
        )
        specialist_role_ids.append(role_id)
        specialists.append(
            {
                "role_id": role_id,
                "upstream_role": upstream_role,
                "purpose": purpose,
                "allowed_actions": allowed_actions,
                "primary_artifact_types": primary_artifact_types,
            }
        )
    _require_unique_strings(specialist_role_ids, field_name="specialists.role_id")
    specialist_role_set = set(specialist_role_ids)
    specialists_by_role = {item["role_id"]: item for item in specialists}

    task_classes_raw = data["task_classes"]
    if not isinstance(task_classes_raw, list) or not task_classes_raw:
        raise FoundationRuleError("task_classes must be a non-empty array")
    task_classes: list[dict] = []
    task_types_seen: list[str] = []
    for index, item in enumerate(task_classes_raw):
        task_class = _require_object(item, subject=f"task_classes[{index}]")
        allowed_keys = {"task_type", "default_owner_role_id", "allowed_actions", "requires_review"}
        required_keys = allowed_keys
        _reject_unknown_keys(task_class, allowed_keys, subject=f"task_classes[{index}]")
        _require_keys(task_class, required_keys, subject=f"task_classes[{index}]")
        task_type = _require_string(task_class["task_type"], field_name=f"task_classes[{index}].task_type")
        if task_type not in TASK_TYPES:
            raise FoundationRuleError(f"task_classes[{index}].task_type is invalid: {task_type}")
        default_owner_role_id = _require_string(
            task_class["default_owner_role_id"],
            field_name=f"task_classes[{index}].default_owner_role_id",
        )
        if default_owner_role_id not in specialist_role_set:
            raise FoundationRuleError(
                f"task_classes[{index}].default_owner_role_id is not a known specialist role: {default_owner_role_id}"
            )
        allowed_actions = _require_string_list(
            task_class["allowed_actions"],
            field_name=f"task_classes[{index}].allowed_actions",
            allow_empty=False,
        )
        _require_unique_strings(allowed_actions, field_name=f"task_classes[{index}].allowed_actions")
        invalid_actions = sorted(set(allowed_actions) - ALLOWED_ACTIONS)
        if invalid_actions:
            raise FoundationRuleError(
                f"task_classes[{index}].allowed_actions contains invalid actions: {', '.join(invalid_actions)}"
            )
        requires_review = _require_bool(task_class["requires_review"], field_name=f"task_classes[{index}].requires_review")
        role_allowed_actions = set(specialists_by_role[default_owner_role_id]["allowed_actions"])
        if not set(allowed_actions).issubset(role_allowed_actions):
            raise FoundationRuleError(
                f"task_classes[{index}] allowed_actions exceed specialist role permissions for {default_owner_role_id}"
            )
        task_types_seen.append(task_type)
        task_classes.append(
            {
                "task_type": task_type,
                "default_owner_role_id": default_owner_role_id,
                "allowed_actions": allowed_actions,
                "requires_review": requires_review,
            }
        )
    _require_unique_strings(task_types_seen, field_name="task_classes.task_type")

    review_policy = _require_object(data["review_policy"], subject="review_policy")
    review_allowed = {"required", "reviewer_role_ids", "close_requires_review"}
    _reject_unknown_keys(review_policy, review_allowed, subject="review_policy")
    _require_keys(review_policy, review_allowed, subject="review_policy")
    reviewer_role_ids = _require_string_list(review_policy["reviewer_role_ids"], field_name="review_policy.reviewer_role_ids")
    _require_unique_strings(reviewer_role_ids, field_name="review_policy.reviewer_role_ids")
    unknown_reviewers = sorted(set(reviewer_role_ids) - specialist_role_set)
    if unknown_reviewers:
        raise FoundationRuleError(
            f"review_policy.reviewer_role_ids contains unknown specialist roles: {', '.join(unknown_reviewers)}"
        )
    normalized_review_policy = {
        "required": _require_bool(review_policy["required"], field_name="review_policy.required"),
        "reviewer_role_ids": reviewer_role_ids,
        "close_requires_review": _require_bool(
            review_policy["close_requires_review"],
            field_name="review_policy.close_requires_review",
        ),
    }
    if normalized_review_policy["required"] and not reviewer_role_ids:
        raise FoundationRuleError("review_policy.required=true requires at least one reviewer_role_id")
    if normalized_review_policy["close_requires_review"] and not normalized_review_policy["required"]:
        raise FoundationRuleError("review_policy.close_requires_review=true requires review_policy.required=true")

    meetings = _require_object(data["meetings"], subject="meetings")
    meetings_allowed = {"enabled", "same_line_only", "default_round_limit"}
    _reject_unknown_keys(meetings, meetings_allowed, subject="meetings")
    _require_keys(meetings, meetings_allowed, subject="meetings")
    same_line_only = _require_bool(meetings["same_line_only"], field_name="meetings.same_line_only")
    if same_line_only is not True:
        raise FoundationRuleError("meetings.same_line_only must be true")
    normalized_meetings = {
        "enabled": _require_bool(meetings["enabled"], field_name="meetings.enabled"),
        "same_line_only": same_line_only,
        "default_round_limit": _require_int(
            meetings["default_round_limit"],
            field_name="meetings.default_round_limit",
            min_value=1,
            max_value=10,
        ),
    }

    sessions = _require_object(data["sessions"], subject="sessions")
    sessions_allowed = {"spawn_strategy", "register_spawned_sessions"}
    _reject_unknown_keys(sessions, sessions_allowed, subject="sessions")
    _require_keys(sessions, sessions_allowed, subject="sessions")
    spawn_strategy = _require_string(sessions["spawn_strategy"], field_name="sessions.spawn_strategy")
    if spawn_strategy not in SPAWN_STRATEGIES:
        raise FoundationRuleError(f"sessions.spawn_strategy is invalid: {spawn_strategy}")
    normalized_sessions = {
        "spawn_strategy": spawn_strategy,
        "register_spawned_sessions": _require_bool(
            sessions["register_spawned_sessions"],
            field_name="sessions.register_spawned_sessions",
        ),
    }

    return {
        "line_id": line_id,
        "objective": objective,
        "scope_notes": scope_notes,
        "orchestrator_role_id": orchestrator_role_id,
        "meeting_moderator_role_id": meeting_moderator_role_id,
        "specialists": specialists,
        "task_classes": task_classes,
        "review_policy": normalized_review_policy,
        "meetings": normalized_meetings,
        "sessions": normalized_sessions,
    }
