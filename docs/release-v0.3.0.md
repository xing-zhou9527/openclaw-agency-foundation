# Release Draft — v0.3.0

## Title

v0.3.0 — External deployment layout and manifest-based loading

## Release summary

This release turns the repository into a cleaner public foundation boundary.
The repo now treats business lines and runtime state as external deployment assets instead of implicitly repo-local content.

## Highlights

### 1. External workdir boundary
The default external deployment home is now:

```text
~/.gency
```

with environment-variable overrides for:

- `GENCY_HOME`
- `GENCY_MANIFEST_ROOT`
- `GENCY_PROMPT_ROOT`
- `GENCY_STATE_ROOT`
- `GENCY_LINES_ROOT`
- `GENCY_REGISTRY_ROOT`
- `GENCY_DEPLOYMENT_MANIFEST`

### 2. Manifest-based business-line loading
Business lines can now be loaded from external manifests such as:

```text
~/.gency/line-packs/<line_id>/manifest.json
```

using:

- `FoundationEngine.from_manifest_dir(...)`
- `FoundationEngine.from_deployment_manifest(...)`

### 3. Deployment manifest layer
A deployment manifest is now part of the public architecture surface.
See:

- `contracts/deployment-manifest.schema.json`
- `config/deployment.example.json`

Default path:

```text
~/.gency/deployment.json
```

### 4. Better public-facing repo shape
The repo now includes clearer public/project-facing assets such as:

- improved `README.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `docs/quickstart.md`
- `docs/first-business-line.md`
- `docs/repo-profile.md`

## Why this release matters

The main structural improvement is boundary clarity:

- foundation code stays in the repo
- deployment assets live outside the repo
- runtime state lives outside the repo

That means the project can be a complete foundation product without needing concrete business lines checked into source control.

## Validation

The smoke path still passes after the boundary changes:

```text
smoke_foundation_ok
```

## Known next steps

- wire real OpenClaw completion events beyond the current workflow model
- decide how far to formalize deployment-manifest capabilities
- expand tests beyond the smoke path
- refine the first public deployment examples
