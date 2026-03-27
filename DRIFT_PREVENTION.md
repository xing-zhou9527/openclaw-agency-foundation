# Drift Prevention

This document explains how the foundation prevents the main controller session from drifting into worker behavior **and** from wrongly treating ordinary conversation as company work.

## The core problem

If the main session is both:
- the user-facing assistant
- and a potentially powerful company orchestrator

then there are two drift risks, not one:

1. **execution drift** — the main session starts doing specialist work itself
2. **activation drift** — the main session starts treating normal chat, coding help, or architecture discussion as company-mode work

The foundation must therefore be **fail-closed**.

## The solution: 7 stacked enforcement layers

## 0. Request-level mode gate before any routing

The main session does **not** start in company mode.
A structured mode decision must happen first.
Ideally that decision is produced by the front-gate skill `request-mode-gate`, then re-validated by the foundation runtime against the same shared contract.

Company mode is allowed only when:
- the request is a real `company_operation`
- the work needs business execution and line ownership
- or the request is explicitly continuing an existing company task

Company mode is denied for:
- general chat
- coding / analysis help outside company execution
- design discussion about the foundation
- meta discussion of how the system should behave

This is the most important new boundary, because it keeps "talking about the company" separate from "running the company workflow".

Relevant files:
- `contracts/session-mode-decision.schema.json`
- `runtime/mode_gate.py`
- `runtime/engine.py`

## 1. Role separation by contract, not by prose

Inside company mode, the main session uses the `ControlTowerCommand` contract.
Workers use the `WorkerResult` contract.

This means the main session is only allowed to emit routing-level outputs such as:
- `dispatch_line`
- `request_line_meeting`
- `query_line_status`
- `close_task`
- `escalate`

It is not allowed to emit worker-style outputs with artifact payloads.

Relevant files:
- `contracts/control-tower-command.schema.json`
- `contracts/worker-result.schema.json`
- `runtime/policy.py`
- `runtime/dispatch.py`
- `runtime/audit.py`

## 2. Runtime validation before execution

The controller layer must validate every control-tower command before it becomes a real action.
If the command is outside the allowlist, or if company mode was not properly activated, execution is rejected.

Examples:
- if the control tower tries to route while still in assistant mode → reject
- if the control tower tries to perform `produce_artifact` → reject
- if a worker result claims cross-line artifacts → reject

Relevant files:
- `runtime/mode_gate.py`
- `runtime/policy.py`
- `runtime/guardrails.py`

## 3. Dispatch-chain restrictions

The allowed chain is:
- main session assistant plane → mode gate
- mode gate → main session control tower plane
- main session control tower plane → line orchestrator
- line orchestrator → same-line specialists
- line orchestrator → same-line meeting moderator

The forbidden chain is:
- assistant plane → direct company task routing without mode activation
- main control tower → specialist artifact work
- line A → line B direct execution
- cross-line meeting without escalation

This removes the two most common drift paths:
- "the central orchestrator just does the work itself"
- "the main session started treating every message as company work"

## 4. Lineage confinement

Company work must not only stay inside the right line; it must stay inside the right company-task lineage.

That means:
- root company work gets a durable `company_task_id`
- child tasks must inherit that `company_task_id`
- child tasks must point back with `parent_task_id`
- the registry must distinguish `last_updated_task_id` from `resume_task_id`
- spawned sessions must bind back to the assigned task and role
- completion events must match the assigned role and registered session binding before the lineage is advanced

This prevents a softer but dangerous drift mode:
> the right line produced the update, but the system cannot prove which task / role / continuation chain it belongs to.

Relevant files:
- `contracts/task.schema.json`
- `contracts/company-task-entry.schema.json`
- `contracts/continuation-resolution.schema.json`
- `runtime/registry.py`
- `runtime/continuation.py`

## 5. Artifact-root confinement

Even if a role tries to drift, the artifact contract limits where outputs can live.
All worker artifacts must sit under the owning line root.
The control tower does not own a line artifact root.

That means a worker can only be considered successful if its outputs validate inside its line.
The main session cannot be treated as a valid producer of line-owned artifacts.

Relevant files:
- `contracts/task.schema.json`
- `runtime/guardrails.py`

## 6. Structured acceptance of worker output

The system should not trust natural-language claims such as:
- "done"
- "implemented"
- "already delivered"

Instead it should only accept structured worker returns that include:
- `task_id`
- `line_id`
- `role_id`
- `status`
- `artifact_paths`
- `next_step`

If the result does not pass validation, it is treated as invalid or drifted output.

## Operational rule for the main session

The main session behaves in one of two ways:

### In assistant mode
- talk normally
- answer questions
- write code / analyze / discuss architecture when appropriate
- do **not** emit control-tower commands

### In company mode
- route
- sequence
- resolve ownership
- request meetings
- report status
- do **not** land the plane for the pilots

## Implementation status

Already implemented in the foundation:

1. a request-level mode gate that separates ordinary assistant work from company-mode operations
2. a dispatcher wrapper that converts company-mode decisions into validated `ControlTowerCommand` objects
3. a worker-result validator for structured specialist returns
4. a post-run audit entry point that flags contract and boundary violations automatically
5. a line task board that stores task mode metadata and allowed next actions by task state
6. an execution adapter (`runtime/engine.py`) that forces company-mode routing decisions through the mode gate + dispatcher wrapper
7. a subagent completion hook (`runtime/hooks.py`) that routes every completion payload through audit before task-state advancement

Still to be built next:

1. automatic wiring from real OpenClaw subagent completion events into the hook layer
2. optional CI tests that simulate activation drift and execution drift attempts and assert rejection
3. generator support so future business lines inherit these guardrails automatically

## Practical standard

The system is working correctly only when these are both true:

> If the main session is just chatting or doing meta work, the foundation should keep it out of company mode.

> If the main session tries to do specialist work directly after company mode is active, the foundation should reject the action before it becomes accepted line output.
