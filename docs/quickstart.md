# Quickstart

This guide gets you from “I just opened the repo” to “I understand the foundation and can safely change it”.

## 1. Understand what this repository is

This project is a foundation for building line-isolated multi-agent operating systems on top of OpenClaw.
It is **not** a ready-made business deployment.

The two most important ideas to keep in mind are:

- the main session stays a normal assistant by default
- company mode must be explicitly activated before control-tower behavior is allowed

If that distinction is fuzzy in your head, stop and read the design docs first.

## 2. Read the key docs in order

Recommended reading order:

1. `../README.md`
2. `../ARCHITECTURE.md`
3. `../DRIFT_PREVENTION.md`
4. `../LINE_CREATION_CHECKLIST.md`

That sequence gives you:
- project scope
- system model
- safety model
- instantiation checklist

## 3. Inspect the core contracts

The contracts in `../contracts/` are the runtime source of truth.
Start with:

- `session-mode-decision.schema.json`
- `control-tower-command.schema.json`
- `task.schema.json`
- `worker-result.schema.json`
- `meeting.schema.json`
- `company-task-entry.schema.json`
- `continuation-resolution.schema.json`

If you are changing behavior that matters, you will almost always touch both a contract and the code that enforces it.

## 4. Inspect the runtime modules

The most important runtime entry points are:

- `../runtime/mode_gate.py`
- `../runtime/engine.py`
- `../runtime/guardrails.py`
- `../runtime/taskboard.py`
- `../runtime/registry.py`
- `../runtime/continuation.py`
- `../runtime/meetingboard.py`
- `../runtime/hooks.py`

A practical mental model:

- `mode_gate.py` decides whether company mode is even legal
- `engine.py` is the orchestration entry point
- `guardrails.py` rejects invalid behavior
- `taskboard.py` stores task-local workflow state
- `registry.py` stores durable lineage and continuation state
- `meetingboard.py` persists meetings and minutes
- `hooks.py` is the completion-ingest boundary

## 5. Run the smoke test

From the repository root:

```bash
python3 scripts/smoke_foundation.py
```

Expected output:

```text
smoke_foundation_ok
```

This is the minimum confidence check that the main flow still works.

## 6. Run a lightweight compile check

```bash
python3 -m compileall runtime scripts
```

This helps catch obvious Python breakage after structural edits.

## 7. Decide what kind of work you are doing

### If you are refining the foundation
Focus on:
- contracts
- runtime enforcement
- tests
- docs

### If you are instantiating the first business line
Jump next to:
- `../config/business-line.example.json`
- `../templates/business-line.template.md`
- `../LINE_CREATION_CHECKLIST.md`
- `./first-business-line.md`

## 8. Safe development loop

A good default loop is:

1. read the relevant contract and runtime file
2. make the smallest change that preserves fail-closed behavior
3. update docs if the behavior changed
4. run the smoke test
5. run compile check
6. only then move to the next change

## 9. Common mistakes to avoid

- treating every request as company work
- letting the control tower produce line-owned artifacts directly
- weakening same-line-only meeting rules
- accepting completion events without strict source binding
- collapsing `resume_task_id` and `last_updated_task_id` into one concept
- changing contracts without updating runtime enforcement

## 10. Where to go next

- Want contribution rules? Read `../CONTRIBUTING.md`
- Want to instantiate the first real line? Read `./first-business-line.md`
- Want the full conceptual model? Read `../ARCHITECTURE.md`
