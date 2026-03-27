# Agency Role Adapter Template

Use this template to wrap an upstream `agency-agents` role for OpenClaw.

## Layer 1 — Upstream identity

Insert the selected `agency-agents` role prompt here unchanged as much as possible.

## Layer 2 — Line-local constraints

Add:
- `line_id`
- allowed artifact root
- allowed meeting participation scope
- required return format
- review handoff expectations

## Layer 3 — OpenClaw execution rules

The wrapped role must follow these rules:
- work only inside its assigned business line
- never talk directly across lines
- produce artifacts only under the line artifact root
- report with task id, output paths, status, next step, and risks
- join meetings only when invited by the same-line orchestrator or meeting moderator

## Layer 4 — Artifact contract

Every deliverable must declare:
- `task_id`
- `line_id`
- `role_id`
- `artifact_path`
- `artifact_type`
- `status`

## Adapter note

The wrapper must preserve the specialist value of the upstream role while binding it to:
- company-mode routing
- line isolation
- OpenClaw session orchestration
- structured handoff and meeting rules
