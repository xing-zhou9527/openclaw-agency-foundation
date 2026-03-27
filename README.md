# OpenClaw Agency Foundation

A fail-closed, OpenClaw-native foundation for building line-isolated multi-agent operating systems.

> This repository is the **foundation layer**, not a ready-made company.  
> It gives you the contracts, guardrails, runtime model, and scaffolding needed to build real business lines on top.

## Why this exists

Most multi-agent systems drift for one of two reasons:

1. the main controller gradually starts doing worker work itself
2. ordinary chat gets silently mistaken for operational execution

This project is built to prevent both.

It treats the primary OpenClaw session as a **dual-plane session**:

- **Assistant plane** — normal chat, coding, analysis, design discussion, private help
- **Company plane** — line-owned operational execution that should be routed, tracked, reviewed, and resumed safely

The key rule is simple:

> The main session may become the Company Control Tower **only when company mode is explicitly activated**.

Outside company mode, it stays a normal assistant.

## Core ideas

### 1. Company mode is activated, not assumed
The system must positively decide that a request belongs to operational execution before any control-tower behavior is legal.

### 2. Control Tower is the main session, not another agent
There is no extra always-on “manager agent” above the user-facing session.
The main session itself acts as the control tower **only inside company mode**.

### 3. Business lines are isolated by default
Prompts, tasks, meetings, artifacts, and session lineage are line-scoped. Cross-line work is denied by default and must be escalated intentionally.

### 4. Runtime contracts matter as much as prompts
This repository relies on both:
- **prompt contracts** for role behavior
- **code contracts** for fail-closed validation

### 5. Continuation is a first-class problem
The system tracks not just “what was updated last”, but also “what should resume next”.
That distinction is explicit in the registry model.

## What you get

- **Mode gating** between ordinary assistant work and company execution
- **Control-tower command contracts** for the main session in company mode
- **Worker result contracts** for specialist outputs
- **Line-local taskboards** with lineage enforcement
- **Authoritative company-task registry** across root tasks, child tasks, sessions, and meetings
- **Structured same-line meetings** with persisted minutes and outcome merge
- **Strict spawned-session binding** for completion events
- **Smoke tests** for the main happy path and key rejection paths
- **Templates and example configs** for instantiating the first business line

## Current status

This repository is currently at the **foundation-ready / instantiation-next** stage.

What is already solid:

- assistant-vs-company separation
- front-gate + back-gate decision model
- control-tower vs worker contract split
- company task lineage via `company_task_id` and `parent_task_id`
- authoritative continuation semantics via `resume_task_id` and `last_updated_task_id`
- same-line meeting lifecycle with persisted minutes
- completion-source validation using registered `source_session_key` + `source_role_id`

What is still intentionally not included:

- real business-line manifests wired into production execution
- generated role packs from `agency-agents`
- real OpenClaw completion-event plumbing beyond the current foundation workflow model
- a production deployment story for a live organization

## Repository layout

```text
openclaw-agency-foundation/
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE
├── ARCHITECTURE.md
├── DRIFT_PREVENTION.md
├── LINE_CREATION_CHECKLIST.md
├── config/
│   ├── foundation.example.json
│   └── business-line.example.json
├── contracts/
│   ├── session-mode-decision.schema.json
│   ├── control-tower-command.schema.json
│   ├── task.schema.json
│   ├── worker-result.schema.json
│   ├── meeting.schema.json
│   ├── business-line-manifest.schema.json
│   ├── company-task-entry.schema.json
│   └── continuation-resolution.schema.json
├── docs/
│   ├── quickstart.md
│   └── first-business-line.md
├── prompts/
│   ├── control-tower.system.md
│   ├── line-orchestrator.system.md
│   ├── meeting-moderator.system.md
│   └── agency-role-adapter.template.md
├── runtime/
│   ├── engine.py
│   ├── mode_gate.py
│   ├── dispatch.py
│   ├── policy.py
│   ├── guardrails.py
│   ├── taskboard.py
│   ├── registry.py
│   ├── continuation.py
│   ├── meetings.py
│   ├── meetingboard.py
│   ├── hooks.py
│   ├── audit.py
│   ├── models.py
│   └── router.py
├── scripts/
│   └── smoke_foundation.py
└── templates/
    └── business-line.template.md
```

## Architecture at a glance

### Dual-plane main session
The primary session can operate in two modes:

- **assistant mode**: answer questions, code, research, discuss architecture
- **company mode**: route operational work into line-owned execution

### Front gate + back gate
A request should ideally pass through two layers:

1. **front gate** — `request-mode-gate` skill produces a `session-mode-decision`
2. **back gate** — the foundation runtime re-validates that same decision before routing

This keeps the system fail-closed even if the prompt layer drifts.

### Task identity model
Two IDs matter:

- `task_id` — a concrete task node currently owned by one role
- `company_task_id` — the durable lineage ID across the whole company workflow

The registry additionally tracks:

- `current_task_id`
- `resume_task_id`
- `last_updated_task_id`
- spawned session bindings
- last completion source

That lets the system answer both:
- “what happened most recently?”
- “what should execute next?”

### Meeting model
Meetings are not free-form role chat.
They are structured workflows with:

- topic
- agenda
- moderator
- participant roles
- round limit
- persisted minutes
- decision summary
- next actions
- unresolved risks

## Quick start

### 1. Read the design docs
Start here:

- `ARCHITECTURE.md`
- `DRIFT_PREVENTION.md`
- `LINE_CREATION_CHECKLIST.md`

### 2. Review the contracts
The contracts are the source of truth for safe orchestration behavior:

- `contracts/session-mode-decision.schema.json`
- `contracts/control-tower-command.schema.json`
- `contracts/task.schema.json`
- `contracts/worker-result.schema.json`
- `contracts/meeting.schema.json`
- `contracts/company-task-entry.schema.json`
- `contracts/continuation-resolution.schema.json`

### 3. Run the smoke test
```bash
python3 scripts/smoke_foundation.py
```

Expected output:

```text
smoke_foundation_ok
```

### 4. Draft your first business line
Use:

- `config/business-line.example.json`
- `templates/business-line.template.md`
- `LINE_CREATION_CHECKLIST.md`

## Example workflow

A typical happy path looks like this:

1. user sends a request
2. mode gate keeps normal chat in assistant mode
3. operational request activates company mode
4. main session routes work to the owning business line
5. line orchestrator creates child tasks with inherited lineage
6. specialists work in spawned sessions
7. completion events are accepted only from registered sources
8. same-line meetings can be opened when alignment is needed
9. meeting outcome is merged back into the task and registry
10. continuation resolves the next executable owner safely

## What this repository is **not**

This is **not**:

- a ready-to-run autonomous company
- a generic chatbot framework
- an always-on global controller agent
- a cross-line free-for-all message bus
- a replacement for explicit operational review

It is a foundation for building those higher-level systems safely.

## Design principles

- **fail closed by default**
- **assistant mode is the default**
- **company mode must be justified**
- **the control tower routes, it does not do worker work**
- **business lines own their own artifacts**
- **meetings are structured workflows, not ad-hoc chaos**
- **continuation must be explicit and auditable**

## Development notes

The current implementation focuses on correctness of the orchestration model:

- schema-backed contracts
- deterministic runtime validation
- file-backed state for tasks, registry, and meetings
- smoke coverage over the main routing / lineage / meeting / continuation flow

If you extend this foundation, keep new capabilities aligned with the same rule:

> If a boundary matters, enforce it in runtime code — not just in prose.

## Recommended next steps

1. freeze the current contracts if you want downstream generators to depend on them
2. build a manifest-to-runtime generator for business lines and role wrappers
3. connect real OpenClaw completion events into the hook path
4. instantiate one business line and validate both happy-path and rejection-path behavior
5. expand tests beyond the current smoke flow

## See also

- `ARCHITECTURE.md` — full system model
- `DRIFT_PREVENTION.md` — why the system resists role drift
- `LINE_CREATION_CHECKLIST.md` — pre-instantiation checklist
- `docs/quickstart.md` — fastest path to understanding the foundation
- `docs/first-business-line.md` — step-by-step guide for instantiating the first real line
- `CONTRIBUTING.md` — contribution workflow and safety expectations
- `CHANGELOG.md` — notable project changes over time
- `LICENSE` — repository license
- `config/foundation.example.json` — example foundation configuration
- `config/business-line.example.json` — example line manifest input
