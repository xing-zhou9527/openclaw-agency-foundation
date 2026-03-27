# First Business Line Creation Checklist

Use this checklist when converting the foundation into the first real business line and agent roster.

## 1. Freeze foundation interfaces first

Do not instantiate a real line until these are considered stable:
- `contracts/session-mode-decision.schema.json`
- `contracts/control-tower-command.schema.json`
- `contracts/task.schema.json`
- `contracts/worker-result.schema.json`
- `contracts/meeting.schema.json`
- `contracts/company-task-entry.schema.json`
- `contracts/continuation-resolution.schema.json`

## 2. Draft the business-line manifest

Create a line manifest based on:
- `contracts/business-line-manifest.schema.json`
- `config/business-line.example.json`
- `templates/business-line.template.md`

Do not proceed until the line has:
- a clear objective
- a bounded scope
- an orchestrator
- a meeting moderator
- a specialist roster
- explicit task classes
- explicit review policy
- explicit meeting policy
- explicit session strategy

## 3. Wrap the agent roles

For every specialist:
- select the upstream `agency-agents` role
- wrap it with `prompts/agency-role-adapter.template.md`
- bind it to the line id
- bind it to the artifact root
- bind it to the worker-result return contract
- document review handoff expectations

## 4. Prepare the line-local file layout

Generate the line roots:
- `lines/<line_id>/workspace`
- `lines/<line_id>/artifacts`
- `lines/<line_id>/meetings`
- `lines/<line_id>/tasks`

Confirm that all artifact-producing roles write only under the line artifact root.

## 5. Decide session behavior

For orchestrator, moderator, and specialists decide:
- on-demand vs persistent sessions
- when sessions should be resumed
- how spawned sessions will be registered in the company-task registry
- how completion events will be tied back to `task_id`, `company_task_id`, and `role_id`

## 6. Rehearse the happy path

Before real usage, prove these pass with the candidate line:
1. request-mode gate stays in assistant mode for non-operational prompts
2. company-mode route creates a root company task
3. line orchestrator creates child tasks with inherited lineage
4. spawned session registration succeeds
5. worker completion updates task state and registry and enforces registered `source_session_key` binding
6. continuation resolution finds the correct `resume_task_id` and owner role
7. meeting open / moderator / persisted minutes / outcome merge flow works for same-line participants

## 7. Rehearse the failure path

Also test rejection paths:
- assistant-mode request tries to route -> reject
- control tower tries to produce artifacts -> reject
- child task with wrong parent or wrong company_task_id -> reject
- cross-line meeting participants -> reject
- completion source role mismatches assigned role -> reject
- continuation request is ambiguous -> require confirmation

## 8. Only then instantiate

When all of the above are true, the first business line is ready to instantiate.
