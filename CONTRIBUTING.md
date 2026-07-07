# Contributing to FieldSight Edge

Thanks for contributing. This repository is meant to be a credible, runnable reference implementation, so changes should improve the product while preserving the honesty of its demo boundaries.

## Principles

- Keep local deterministic mode runnable without cloud credentials, GPUs, or paid services.
- Preserve tenant scoping, auditability, and explicit demo-data labeling.
- Avoid fake production claims, invented benchmarks, or undocumented external dependencies.
- Prefer small, focused pull requests with tests or verification notes.

## Local setup

### API

```bash
cd apps/api
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
$env:PYTHONPATH='.'
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python scripts\seed_demo.py
```

### Web

```bash
cd apps/web
npm ci
```

## Required checks

Run the checks relevant to your change before opening a pull request.

```bash
cd apps/api
$env:PYTHONPATH='.'
.venv\Scripts\python -m ruff check app tests scripts
.venv\Scripts\python -m pytest -q

cd ../web
npm run lint
npm run typecheck
npm run build
npm run test:e2e
```

If you change the seeded workflows or presentation routes, also refresh the browser screenshots:

```bash
cd apps/web
npm run capture:screens
```

## Pull request guidance

- Describe what changed and why.
- Call out any workflow, schema, or seeded-data impacts.
- Mention which commands you ran and whether they passed.
- Update the README or docs when setup, behavior, or limitations change.

## Scope boundaries

Production integrations such as PostGIS, Redis workers, object storage, Slack, GIS, ERP, CMMS, YOLO, ONNX, and remote inference are valid extension points, but they must remain clearly documented as optional or environment-dependent unless fully wired and verified in the repository.
