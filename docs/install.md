# Installation Guide

This project is currently a source-first foundation repo.
It is not packaged as a pip library yet, so "install" currently means:

1. clone the repository
2. prepare Python
3. choose or confirm your external deployment home
4. verify the smoke path

## Requirements

Minimum practical requirements:

- Git
- Python 3.10+
- a writable external workdir (default `~/.gency`)

Current note:

- the foundation runtime and smoke path currently use only Python standard-library modules
- there is no third-party Python dependency step required for the current smoke flow

## 1. Clone the repository

```bash
git clone git@github.com:xing-zhou9527/openclaw-agency-foundation.git
cd openclaw-agency-foundation
```

Or with HTTPS:

```bash
git clone https://github.com/xing-zhou9527/openclaw-agency-foundation.git
cd openclaw-agency-foundation
```

## 2. Confirm Python is available

```bash
python3 --version
```

If you are on macOS or Linux and want to be explicit:

```bash
python3 -m compileall runtime scripts
```

## 3. Choose the external deployment home

Default external workdir:

```text
~/.gency
```

Default layout:

```text
~/.gency/
├── deployment.json
├── line-packs/
│   └── <line_id>/
│       └── manifest.json
├── prompt-packs/
└── state/
    ├── registry/
    └── lines/
```

Optional environment variables:

```bash
export GENCY_HOME="$HOME/.gency"
export GENCY_DEPLOYMENT_MANIFEST="$GENCY_HOME/deployment.json"
export GENCY_MANIFEST_ROOT="$GENCY_HOME/line-packs"
export GENCY_PROMPT_ROOT="$GENCY_HOME/prompt-packs"
export GENCY_STATE_ROOT="$GENCY_HOME/state"
export GENCY_LINES_ROOT="$GENCY_STATE_ROOT/lines"
export GENCY_REGISTRY_ROOT="$GENCY_STATE_ROOT/registry"
```

You only need to set these if you want to override defaults.

## 4. Review the example configs

Start from these files in the repo:

- `config/foundation.example.json`
- `config/deployment.example.json`
- `config/business-line.example.json`

Typical first step:

```bash
mkdir -p ~/.gency/line-packs/marketing
cp config/deployment.example.json ~/.gency/deployment.json
cp config/business-line.example.json ~/.gency/line-packs/marketing/manifest.json
```

Then edit them to match your actual deployment.

## 5. Run the smoke test

From the repository root:

```bash
python3 scripts/smoke_foundation.py
```

Expected output:

```text
smoke_foundation_ok
```

This is the fastest way to verify that:

- the repo is usable
- the current runtime entrypoints still work
- the deployment-manifest boundary has not regressed

## 6. Recommended next reads

After installation, continue in this order:

1. `README.md`
2. `ARCHITECTURE.md`
3. `DRIFT_PREVENTION.md`
4. `docs/quickstart.md`
5. `docs/first-business-line.md`

## Troubleshooting

### Smoke test fails

Start with:

```bash
python3 -m compileall runtime scripts
```

Then re-run:

```bash
python3 scripts/smoke_foundation.py
```

### I do not want to use `~/.gency`

Set one or more of:

- `GENCY_HOME`
- `GENCY_DEPLOYMENT_MANIFEST`
- `GENCY_MANIFEST_ROOT`
- `GENCY_PROMPT_ROOT`
- `GENCY_STATE_ROOT`
- `GENCY_LINES_ROOT`
- `GENCY_REGISTRY_ROOT`

### I want the full deployment entrypoint

Use:

- `FoundationEngine.from_deployment_manifest(...)`

### I only want to load line manifests directly

Use:

- `FoundationEngine.from_manifest_dir(...)`
