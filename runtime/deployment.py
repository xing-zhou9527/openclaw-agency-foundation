from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .guardrails import FoundationRuleError


GENCY_HOME_ENV = "GENCY_HOME"
GENCY_MANIFEST_ROOT_ENV = "GENCY_MANIFEST_ROOT"
GENCY_PROMPT_ROOT_ENV = "GENCY_PROMPT_ROOT"
GENCY_STATE_ROOT_ENV = "GENCY_STATE_ROOT"
GENCY_LINES_ROOT_ENV = "GENCY_LINES_ROOT"
GENCY_REGISTRY_ROOT_ENV = "GENCY_REGISTRY_ROOT"
GENCY_DEPLOYMENT_MANIFEST_ENV = "GENCY_DEPLOYMENT_MANIFEST"

DEFAULT_GENCY_HOME = "~/.gency"
DEFAULT_DEPLOYMENT_MANIFEST = "deployment.json"


@dataclass(frozen=True)
class DeploymentLayout:
    home: Path
    manifest_root: Path
    prompt_root: Path
    state_root: Path
    lines_root: Path
    registry_root: Path


@dataclass(frozen=True)
class DeploymentManifest:
    path: Path
    payload: dict


def _expand_path(value: str | Path) -> Path:
    return Path(os.path.expandvars(str(value))).expanduser()


def resolve_deployment_manifest_path(
    *,
    manifest_path: str | Path | None = None,
    home: str | Path | None = None,
) -> Path:
    resolved_home = _expand_path(home or os.environ.get(GENCY_HOME_ENV, DEFAULT_GENCY_HOME))
    return _expand_path(
        manifest_path
        or os.environ.get(GENCY_DEPLOYMENT_MANIFEST_ENV, str(resolved_home / DEFAULT_DEPLOYMENT_MANIFEST))
    )


def load_deployment_manifest(
    *,
    manifest_path: str | Path | None = None,
    home: str | Path | None = None,
) -> DeploymentManifest:
    path = resolve_deployment_manifest_path(manifest_path=manifest_path, home=home)
    if not path.exists():
        raise FoundationRuleError(f"deployment manifest not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FoundationRuleError(f"invalid deployment manifest json: {path}") from exc
    if not isinstance(payload, dict):
        raise FoundationRuleError(f"deployment manifest must be an object: {path}")
    return DeploymentManifest(path=path, payload=payload)


def resolve_deployment_layout(
    *,
    home: str | Path | None = None,
    manifest_root: str | Path | None = None,
    prompt_root: str | Path | None = None,
    state_root: str | Path | None = None,
    lines_root: str | Path | None = None,
    registry_root: str | Path | None = None,
    defaults: Mapping[str, str | Path] | None = None,
) -> DeploymentLayout:
    """Resolve the external deployment/workdir layout.

    The foundation repo is product code only. Business-line packs, prompt packs,
    and runtime state should live in an external workdir, defaulting to `~/.gency`.

    Override order for every path is:
    1. explicit function argument
    2. dedicated environment variable
    3. deployment/defaults mapping
    4. derived default under `GENCY_HOME`
    5. fallback default `~/.gency`
    """

    defaults = defaults or {}
    resolved_home = _expand_path(
        home
        or os.environ.get(GENCY_HOME_ENV)
        or defaults.get("home")
        or DEFAULT_GENCY_HOME
    )
    resolved_manifest_root = _expand_path(
        manifest_root
        or os.environ.get(GENCY_MANIFEST_ROOT_ENV)
        or defaults.get("manifest_root")
        or (resolved_home / "line-packs")
    )
    resolved_prompt_root = _expand_path(
        prompt_root
        or os.environ.get(GENCY_PROMPT_ROOT_ENV)
        or defaults.get("prompt_root")
        or (resolved_home / "prompt-packs")
    )
    resolved_state_root = _expand_path(
        state_root
        or os.environ.get(GENCY_STATE_ROOT_ENV)
        or defaults.get("state_root")
        or (resolved_home / "state")
    )
    resolved_lines_root = _expand_path(
        lines_root
        or os.environ.get(GENCY_LINES_ROOT_ENV)
        or defaults.get("lines_root")
        or (resolved_state_root / "lines")
    )
    resolved_registry_root = _expand_path(
        registry_root
        or os.environ.get(GENCY_REGISTRY_ROOT_ENV)
        or defaults.get("registry_root")
        or (resolved_state_root / "registry")
    )
    return DeploymentLayout(
        home=resolved_home,
        manifest_root=resolved_manifest_root,
        prompt_root=resolved_prompt_root,
        state_root=resolved_state_root,
        lines_root=resolved_lines_root,
        registry_root=resolved_registry_root,
    )
