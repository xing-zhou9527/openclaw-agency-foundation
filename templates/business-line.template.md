# Business Line Template

Use this template when instantiating the first real business line from the foundation.
Do not skip fields: this template is meant to become the human-readable companion to a machine-validated business-line manifest.

## 1. Line identity

- `line_id`:
- `objective`:
- `scope_notes`:
  -
  -

## 2. Core control roles

- `orchestrator_role_id`:
- `meeting_moderator_role_id`:

## 3. Specialist roster

Add one block per specialist.

### Specialist
- `role_id`:
- `upstream_role` (from `agency-agents`):
- `purpose`:
- `allowed_actions`:
  - `produce_artifact` and/or `review_artifact`
  - optional `request_meeting`
  - optional `escalate`
- `primary_artifact_types`:
  -
  -
- `review_handoff_to`:

## 4. Task classes

Define the task classes the orchestrator may create.

### Task class
- `task_type`:
- `default_owner_role_id`:
- `allowed_actions`:
- `requires_review`:
- `done_definition`:

## 5. Review policy

- `required`:
- `reviewer_role_ids`:
  -
- `close_requires_review`:
- `reopen_rule`:

## 6. Meeting policy

- `enabled`: true/false
- `same_line_only`: true
- `default_round_limit`:
- `when_to_open_meeting`:
  - multi-role disagreement
  - blocked dependency
  - design / implementation / review convergence
- `meeting_output_requirements`:
  - decision summary
  - next actions with owners
  - unresolved risks
  - minutes path

## 7. Artifact policy

- `artifact_root`:
- `allowed_subfolders`:
  - drafts/
  - reviews/
  - final/
- `forbidden_paths`:
  - cross-line roots
  - shared roots without explicit escalation
- `artifact_naming_rule`:

## 8. Session strategy

- `spawn_strategy`: `on_demand` or `persistent`
- `register_spawned_sessions`: true/false
- `session_resume_rule`:
- `completion_binding_rule`:

## 9. Readiness checklist

Before calling a line “ready”, confirm all are true:
- specialists map to real upstream `agency-agents` roles
- all role ids are unique inside the line
- every task class has a default owner
- review policy is explicit
- meeting policy is explicit
- artifact root and folder rules are explicit
- spawn / resume strategy is explicit
- a business-line manifest JSON can be generated and validated against `contracts/business-line-manifest.schema.json`
