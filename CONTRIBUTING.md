# Contributing to OpenClaw Agency Foundation

Thanks for contributing.

This repository is not a generic chatbot playground. It is a fail-closed orchestration foundation, so small changes can have large behavioral consequences. Please optimize for clarity, traceability, and boundary safety.

## Project goal

The goal of this project is to make it safe to build line-isolated multi-agent operating systems on top of OpenClaw.

That means contributions should preserve three core properties:

1. **ordinary assistant work must stay out of company mode unless explicitly activated**
2. **the control tower must not drift into worker behavior**
3. **line-owned execution must remain auditable through contracts, lineage, and runtime checks**

## Before you change anything

Please read these first:

- `README.md`
- `ARCHITECTURE.md`
- `DRIFT_PREVENTION.md`
- `LINE_CREATION_CHECKLIST.md`

If your change touches schemas, routing, guardrails, meetings, task lineage, or continuation semantics, read the relevant files in `contracts/` and `runtime/` before editing.

## What kinds of contributions are welcome

Good contributions include:

- tightening runtime guardrails
- clarifying contracts and schemas
- improving docs and onboarding flow
- adding deterministic tests
- improving business-line instantiation scaffolding
- improving continuation, meeting, and task lineage safety

Be careful with changes that:

- weaken fail-closed behavior
- make company mode easier to activate by accident
- let the main session produce line-owned artifacts directly
- blur cross-line boundaries
- accept unstructured worker results in places where schemas should decide

## Development workflow

From the repository root, use a small safe loop:

```bash
python3 scripts/smoke_foundation.py
python3 -m compileall runtime scripts
```

The smoke test is the minimum bar for behavioral sanity. If it fails, do not assume the change is safe.

## Change guidelines

### 1. Preserve the architectural split
Keep the distinction between:

- assistant plane
- company plane
- control-tower commands
- worker results
- line-local execution
- continuation state

If your change blurs these boundaries, explain why in the PR.

### 2. Update contracts and runtime together
If you change a contract, also update the runtime code that enforces it.
If you change runtime behavior, update the relevant schema or documentation.

### 3. Prefer explicit validation over prompt-only behavior
If a rule matters, try to enforce it in code.
Do not rely only on prompt wording for safety-critical boundaries.

### 4. Keep meetings structured
Meetings are coordination workflows, not free-form multi-agent chat.
Changes should preserve topic, agenda, participant, outcome, and minutes semantics.

### 5. Keep continuation auditable
If you change lineage or continuation logic, preserve the distinction between:

- `current_task_id`
- `resume_task_id`
- `last_updated_task_id`

Do not collapse them unless the model itself changes everywhere consistently.

## Pull request checklist

Before opening a PR, confirm:

- [ ] docs still match actual behavior
- [ ] touched schemas and runtime files are aligned
- [ ] smoke test passes
- [ ] compile check passes
- [ ] new failure paths are covered if you changed guardrails
- [ ] no new cross-line or control-tower drift path was introduced

## If you are adding the first real business line

Please do not skip the dedicated process. Use:

- `config/business-line.example.json`
- `templates/business-line.template.md`
- `LINE_CREATION_CHECKLIST.md`
- `docs/first-business-line.md`

## Style notes

- prefer simple, explicit names
- keep contracts human-readable
- document why a boundary exists, not just what it is
- optimize for future auditability over cleverness

## License

By contributing, you agree that your contributions will be licensed under the repository license.
