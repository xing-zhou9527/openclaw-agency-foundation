# Changelog

All notable changes to this project will be documented in this file.

The format loosely follows Keep a Changelog, and versioning can evolve as the foundation stabilizes.

## [Unreleased]

### Added
- GitHub-style repository housekeeping files: `CONTRIBUTING.md`, `LICENSE`, `docs/quickstart.md`, and `docs/first-business-line.md`
- A clearer onboarding path for new contributors and first-line instantiation work
- `runtime/deployment.py` for resolving the external deployment/workdir layout
- `runtime/line_loader.py` for loading business-line definitions from external line-pack manifests

### Changed
- `README.md` was rewritten into a more complete open-source project homepage with architecture, scope, workflow, and next-step guidance
- the default deployment boundary now treats `~/.gency` as the external home for line packs, prompt packs, and runtime state, with environment-variable overrides
- `FoundationEngine` now supports manifest-based external deployment initialization instead of assuming repo-local line state
- synthesized line templates are explicitly treated as smoke/demo helpers rather than the intended production boundary
- `scripts/smoke_foundation.py` now exercises manifest-based loading from an external workdir layout

## [0.2.0] - 2026-03-26

### Added
- dual-plane session model: assistant plane vs company plane
- shared `session-mode-decision` contract between front gate and runtime back gate
- authoritative company-task lineage via `company_task_id` and `parent_task_id`
- continuation semantics with explicit `resume_task_id` and `last_updated_task_id`
- persisted same-line meeting lifecycle with minutes and outcome merge
- strict completion-source binding using registered `source_session_key` and `source_role_id`
- business-line manifest schema, example config, and human-readable template
- first-line creation checklist
- end-to-end smoke test covering routing, lineage, meetings, completion, and continuation

### Changed
- control-tower behavior was tightened so company-mode actions require explicit activation and validated routing
- the foundation was repositioned as a reusable base layer rather than an implicitly always-on control tower
