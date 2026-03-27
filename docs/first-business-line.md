# First Business Line Guide

This guide turns the foundation into its first real business line without skipping the safety model.

Important boundary: the first real line should be created as an external deployment asset, not as committed runtime content inside this repo.
By default, put it under `~/.gency` unless you override the deployment roots with environment variables.

Use it together with:

- `../LINE_CREATION_CHECKLIST.md`
- `../config/business-line.example.json`
- `../templates/business-line.template.md`

## Default external layout

A reasonable default is:

```text
~/.gency/
├── line-packs/
├── prompt-packs/
└── state/
    ├── registry/
    └── lines/
```

Suggested env overrides when needed:

- `GENCY_HOME`
- `GENCY_MANIFEST_ROOT`
- `GENCY_PROMPT_ROOT`
- `GENCY_STATE_ROOT`
- `GENCY_LINES_ROOT`
- `GENCY_REGISTRY_ROOT`

## Goal

By the end of this process, you should have:

- one clearly scoped line
- one orchestrator
- one meeting moderator
- a small specialist roster
- explicit task classes
- explicit review policy
- explicit meeting policy
- explicit artifact boundaries
- explicit session strategy

Do **not** optimize for breadth on the first line. Optimize for auditable behavior.

## Step 1. Pick a narrow line

Start with a line that is easy to reason about.
A good first line usually has:

- one clear objective
- one obvious review path
- few artifact types
- mostly same-line coordination

Example shape:

- marketing content line
- research synthesis line
- internal documentation line

Avoid choosing a line whose first version already needs complex cross-line execution.

## Step 2. Define line identity

Fill out the human-readable template in `../templates/business-line.template.md`.

At minimum, define:

- `line_id`
- `objective`
- `scope_notes`
- `orchestrator_role_id`
- `meeting_moderator_role_id`

Your scope notes should make it obvious what the line does **not** own.

## Step 3. Build the specialist roster

Start small.
For the first line, 2–4 specialists is usually enough.

For each specialist, define:

- `role_id`
- upstream role source from `agency-agents`
- purpose
- allowed actions
- primary artifact types
- review handoff target

Good first-line specialist patterns look like:

- producer + reviewer
- researcher + writer + reviewer
- operator + analyst + reviewer

## Step 4. Define task classes

For each task class, decide:

- who owns it by default
- what actions are allowed
- whether review is required
- what “done” means

Keep task classes concrete.
A bad task class is too vague, like `work`.
A better task class names the workflow shape, like `build`, `review`, or `research`.

## Step 5. Lock review policy

Do not leave review implicit.
Define:

- whether review is required
- which role ids may review
- whether task closure requires review
- when a task must reopen after review feedback

If review is fuzzy, the first real line will drift quickly.

## Step 6. Lock meeting policy

Meetings are for structured convergence, not casual coordination.
Decide:

- whether meetings are enabled
- same-line-only rule
- default round limit
- what triggers a meeting
- what outputs every meeting must produce

Every meeting should end with durable outcomes such as:

- decision summary
- next actions with owners
- unresolved risks
- minutes path

## Step 7. Lock artifact policy

Your line must own its own artifact space.
Define:

- artifact root
- allowed subfolders
- forbidden paths
- naming rule

The first version can stay simple, for example:

- `drafts/`
- `reviews/`
- `final/`

The important part is not the naming style. The important part is line confinement.

## Step 8. Decide session strategy

For orchestrator, moderator, and specialists, define:

- on-demand vs persistent sessions
- when sessions may be resumed
- how spawned sessions are registered
- how completion events bind back to task and role identity

The foundation assumes completion events must be traceable.
If your session strategy makes that ambiguous, tighten it before proceeding.

## Step 9. Mirror the template into a machine-readable manifest

Once the human-readable template is clear, create the machine-readable line manifest as external deployment content based on:

- `../contracts/business-line-manifest.schema.json`
- `../config/business-line.example.json`

The human template and JSON manifest should say the same thing from two angles:

- one for humans reviewing intent
- one for runtime and tooling validation

Recommended default location:

```text
~/.gency/line-packs/<line_id>/manifest.json
```

## Step 10. Rehearse the happy path

Before using the line for real work, prove the main path works:

1. assistant-mode request stays out of company mode
2. company-mode request creates a root company task
3. orchestrator creates child tasks with inherited lineage
4. spawned session registration works
5. worker completion advances state only when the registered source matches
6. continuation resolves the correct `resume_task_id`
7. same-line meeting open and outcome merge works

Use the existing foundation smoke flow as the baseline sanity check:

```bash
python3 scripts/smoke_foundation.py
```

## Step 11. Rehearse the rejection path

Also prove the line rejects unsafe behavior:

- assistant-mode routing attempt
- control tower trying to produce artifacts
- wrong `company_task_id` or wrong parent lineage
- cross-line meeting attempt
- wrong completion source
- ambiguous continuation request

The first line is only “ready” when both the happy path and the refusal path are believable.

## Step 12. Keep the first line boring

That is a compliment.

A good first line is:

- small
- explicit
- reviewable
- easy to resume
- easy to reject when something is wrong

Once that works, then expand roster size, automation depth, and orchestration complexity.

## Recommended first-line checklist

Before calling the line ready, confirm:

- the line objective is narrow
- every role id is unique
- every task class has a default owner
- review policy is explicit
- meeting policy is explicit
- artifact root is explicit
- session strategy is explicit
- lineage and continuation semantics are preserved
- the line still fits the foundation’s fail-closed model

## After the first line works

Only then should you start thinking about:

- manifest-to-prompt generation
- richer tests
- real completion-event wiring
- second-line instantiation
- controlled cross-line escalation patterns
