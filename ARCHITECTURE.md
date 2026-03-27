# Architecture

## 1. Objective

Build an OpenClaw-adapted multi-agent foundation where:
- the **main session stays a normal assistant by default**
- the **same main session can enter company mode when the user wants real operational execution**
- **Company Control Tower is the main controller session itself while company mode is active**
- **business lines** are first-class isolated units
- **specialist roles** come from `agency-agents`
- same-line roles can hold structured meetings
- code enforces the most important boundaries instead of relying only on prompt discipline

## 2. Core design principles

### A. Dual-plane main session
The main session has two operating planes:
- **assistant plane** — normal chat, coding help, analysis, Q&A, private help, architecture discussion
- **company plane** — line-owned operational execution that should be routed into the company workflow

This means the system must not treat every user message as company work.
Talking about the company system is not the same as using the company system.

### B. Company mode is activated, not assumed
The foundation must positively activate company mode before any control-tower action is legal.

A request should enter company mode only when it is truly operational, for example:
- the user wants the agent to actually run a business workflow
- the work needs a business-line owner
- the work should create durable line-owned tasks / artifacts / meetings
- the request is continuing an existing company task

A request should stay in assistant mode when it is:
- ordinary chat
- coding or research help outside company execution
- design discussion about the foundation itself
- Q&A about how the system should work
- personal help that does not need business-line ownership

Ambiguous cases should fail closed: stay in assistant mode or ask for clarification.

### C. Control Tower is the main session, not another agent
This remains the most important structural rule.

**Company Control Tower is the primary OpenClaw session itself, but only inside company mode.**
It is not a spawned agent, not a separate controller runtime, and not an extra decision layer.

That means the main session may:
- receive user requests
- classify whether a request belongs to assistant mode or company mode
- when company mode is active, open / close task records
- dispatch line orchestrators
- request meetings
- aggregate status

It must not:
- assume every message belongs to company mode
- write business deliverables directly once a request is inside company mode
- claim ownership of line artifacts
- bypass line orchestrators once work is inside a line

### D. Line isolation is the default security model
Each business line is an isolated execution domain.
Isolation covers:
- prompts
- task boards
- meetings
- artifacts
- memory
- session lineage

A role from line A cannot directly produce or mutate artifacts for line B.

### E. Roles are imported, then wrapped
`agency-agents` provides upstream role identities and workflows.
The foundation wraps them with OpenClaw-specific constraints:
- line identity
- artifact rules
- meeting protocol
- return schema
- escalation behavior

So the final role prompt is:
1. upstream role prompt from `agency-agents`
2. line-local constraints
3. artifact and meeting contract
4. OpenClaw orchestration rules

### F. Meetings are first-class workflows
Meetings are not ad-hoc chat.
They are structured coordination rounds with:
- agenda
- participants
- moderator
- round limits
- decision output
- minutes

### G. Foundation repo, deployment assets, and runtime state must be separate
The foundation repo is the product codebase.
It should not be considered incomplete just because no concrete business line has been instantiated inside it.

Three layers should stay distinct:
- **foundation code** — schemas, runtime, validators, adapters, templates, docs
- **deployment assets** — business-line manifests, role packs, prompt packs
- **runtime state** — tasks, meetings, artifacts, registry, spawned-session bindings

Default external workdir:
- `~/.gency`

Default override model:
- `GENCY_HOME`
- optional granular overrides such as `GENCY_MANIFEST_ROOT`, `GENCY_PROMPT_ROOT`, `GENCY_STATE_ROOT`, `GENCY_LINES_ROOT`, `GENCY_REGISTRY_ROOT`

## 3. Runtime topology

### Layer 0 — Foundation kernel
Lives in this directory only.
Contains:
- schemas
- mode gating logic
- routing logic
- validators
- prompt templates
- authoritative registry / continuation logic
- future generators

### Layer 0.5 — External deployment/workdir
Lives outside the repo, defaulting to `~/.gency` unless overridden by environment variables.
Contains:
- business-line manifests
- generated role packs
- generated prompt packs
- runtime state roots

This is where concrete line instances belong.
It is not a sign that the foundation repo is incomplete if these assets do not exist yet.

### Layer 1 — Main-session assistant plane
This is the default behavior of the primary session.
Responsibilities:
- talk normally with the user
- answer questions
- do private coding / analysis work when appropriate
- discuss or modify the foundation itself
- decide whether a request should even be considered for company mode

This layer must **not** emit control-tower commands.

### Layer 2 — Main-session company control tower plane
This is still the same primary session, but only after the mode gate activates company mode.
Responsibilities:
- classify operational requests
- decide which business line owns the request
- open or update company task records
- dispatch the line orchestrator
- request intra-line meetings
- summarize status back to the user

Important: this layer is **not instantiated as a separate agent**.
It is an operating plane plus a guardrail set for the main controller session.

### Layer 3 — Business line orchestrator (template, not instantiated yet)
One orchestrator per business line.
Responsibilities:
- break line-owned tasks into slices
- assign slices to specialists in the same line
- request same-line meetings
- enforce review order within the line
- maintain line-local status

### Layer 4 — Specialist roles (template, not instantiated yet)
Workers adapted from `agency-agents`.
Responsibilities:
- perform specialist work
- produce artifacts
- report in structured format
- participate in meetings when invited

### Layer 5 — Meeting moderator (template, not instantiated yet)
A line-local coordination role.
Responsibilities:
- run structured meetings
- collect participant positions
- detect disagreement / blockers
- produce minutes and decision records

## 4. Mode-gate contract

The foundation introduces a request-level mode gate.
A structured `session-mode-decision` is produced before company-mode actions are allowed.

Recommended operating model:
- the front-gate skill `skills/request-mode-gate/` makes the first fail-closed decision
- the foundation runtime re-validates the same contract before routing

The shared mode-decision contract answers:
- what kind of request this is
- whether the session should stay in assistant mode or enter company mode
- whether control-tower actions are allowed
- whether business execution and line ownership are actually present
- whether the activation is request-scoped or a safe continuation of an existing company task
- whether clarification is required

This prevents the dangerous shortcut:
> “Because the main session *can* be a control tower, it starts behaving like one for every message.”

## 5. OpenClaw adaptation model

The foundation assumes OpenClaw native primitives for execution:
- `sessions_spawn`
- `subagents`
- `sessions_send`
- `sessions_history`
- file-backed workspace state

### Recommended execution pattern
- The main controller session receives the user request
- The mode gate decides assistant plane vs company plane
- If the request stays in assistant mode, the main session handles it normally
- If company mode is activated, the main session acts as the control tower
- The control tower dispatches the owning line orchestrator
- The line orchestrator dispatches same-line specialists
- If cross-role debate is needed, the line orchestrator opens a meeting workflow
- The meeting moderator coordinates the meeting and returns minutes
- The line orchestrator resumes task slicing after the meeting
- The main controller session only reports status and routing outcomes upward

## 5.1 Authoritative task identity and continuation

Inside company mode, task identity is split into two levels:
- `task_id` — a concrete task node handled by one owner at one point in the workflow
- `company_task_id` — the durable lineage id that ties root task, child tasks, spawned sessions, meetings, and continuation resolution together

This exists to answer, deterministically:
- which root request this child task belongs to
- which concrete task was updated most recently (`last_updated_task_id`)
- which concrete task should be resumed next (`resume_task_id`)
- which role owns the next executable step
- which spawned session is associated with that work
- which completion source last updated the lineage

`parent_task_id` links child tasks back to the current owning task.
The registry stores the durable company-task view while the line task board stores task-local state.

## 6. Isolation model

### Namespace rule
Every business line owns a unique namespace, for example:
- `line:<line_id>`
- `artifact:<line_id>:...`
- `meeting:<line_id>:...`
- `task:<line_id>:...`

### Path rule
Every artifact path must remain under the owning line root.
No worker can write outside its line root except to explicitly allowed shared foundation paths.

### Messaging rule
Direct worker-to-worker communication is allowed only when:
- both roles belong to the same line
- the meeting or task contract explicitly allows it

Cross-line communication is denied by default and must be escalated through the main controller session.

## 7. Meetings

Same-line meetings are required to satisfy the “different roles can hold meetings” requirement.

### Meeting triggers
A line orchestrator opens a meeting when:
- two or more roles need alignment
- the task is blocked by disagreement
- design / implementation / review must converge before continuing
- a delivery risk requires structured consensus

### Meeting mechanism
The meeting should run as a moderator-driven structured workflow, not as uncontrolled free chat.
Preferred topology:
- orchestrator opens the meeting
- a persisted meeting record is created under the line meeting root
- moderator collects structured positions from participants
- moderator summarizes agreement / disagreement
- moderator decides whether another round is needed
- moderator emits durable minutes and a decision summary
- the meeting outcome is merged back into the parent task
- orchestrator resumes task slicing based on the meeting output

### Meeting format
A meeting contains:
- `meeting_id`
- `line_id`
- `topic`
- `agenda`
- `moderator_role`
- `participant_roles`
- `round_limit`
- `minutes_path`
- `decision_summary`
- `next_actions`

## 8. Prompt system

The prompt layer is split into five classes:

### 1. Assistant-plane operating behavior
This is the ordinary main-session behavior outside company mode.

### 2. Mode-gate decision behavior
This determines whether a request should remain ordinary assistant work or become company work.

### 3. Control Tower operating prompt
This applies only after company mode has been activated.
It is not a separate spawned agent prompt.

### 4. Line orchestrator prompt
Owns task decomposition and same-line coordination.

### 5. Meeting moderator prompt
Runs structured multi-role meetings and emits minutes.

### 6. Agency role adapter template
Wraps upstream `agency-agents` roles with line isolation and OpenClaw contracts.

## 9. Code-backed guardrails

The runtime code enforces the architectural boundaries.
Examples:
- reject company-mode routing when the mode gate did not activate company mode
- reject tasks whose executor is the main-session control tower
- reject meetings with cross-line participants
- reject artifact paths outside the line root
- reject direct worker outputs without task IDs
- reject cross-line artifact references without explicit escalation
- reject control-tower commands that are outside the routing-only command set
- reject company tasks that do not carry activation metadata

This is the key difference between a real foundation and “just a pile of prompts”.

## 10. Drift prevention model

To stop the main controller session from drifting into business execution, the foundation uses six layers together:
- a request-level mode gate that keeps ordinary chat out of company mode
- a dedicated `ControlTowerCommand` contract for company mode
- a separate `WorkerResult` contract for specialists
- runtime validation before command execution
- dispatch-chain restrictions (main session -> line orchestrator -> specialists)
- artifact-root confinement and structured result acceptance

The detailed reasoning and enforcement model live in `DRIFT_PREVENTION.md`.

## 11. Directory policy

All foundation assets stay inside this single directory so that later you can:
- version it cleanly
- ship it as a standalone repo
- generate line-specific runtime assets from one source of truth

## 12. What comes next

Phase 1 — Foundation stabilization
- finalize mode-gate / command / task contracts
- finalize prompt contracts
- finalize guardrail code

Phase 2 — Generator layer
- import `agency-agents` roles into wrapped prompts
- generate line-local role packs
- generate OpenClaw config fragments

Phase 3 — Instantiation
- create the first real business line
- attach real roles
- test meetings, routing, and review flow
