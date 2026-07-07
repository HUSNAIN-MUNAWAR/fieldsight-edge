# Verification record

This record lists commands and outcomes executed in this workspace on **July 8, 2026**.

## Passed

| Check | Command / flow | Actual result |
| --- | --- | --- |
| API dependency install | `py -3.12 -m venv .venv` then `.venv\Scripts\pip install -r requirements.txt` | Passed. Python 3.12 environment created and backend dependencies installed. |
| Frontend dependency install | `npm ci --no-fund --no-audit` | Passed after normalizing the lockfile to the public npm registry. |
| Fresh migration | `$env:DATABASE_URL='sqlite:///./.data/launch.db'; $env:PYTHONPATH='.'; .venv\Scripts\python -m alembic upgrade head` | Passed through Alembic head `20260707_02`. |
| Idempotent seed | `$env:DATABASE_URL='sqlite:///./.data/launch.db'; $env:PYTHONPATH='.'; .venv\Scripts\python scripts\seed_demo.py` | Passed. Demo workspace seeded successfully. |
| Migration status | `$env:DATABASE_URL='sqlite:///./.data/launch.db'; $env:PYTHONPATH='.'; .venv\Scripts\python scripts\migration_status.py` | Passed and reported SQLite with Alembic head `20260707_02`. |
| Backend lint | `$env:PYTHONPATH='.'; .venv\Scripts\python -m ruff check app tests scripts` | Passed. |
| Backend tests | `$env:PYTHONPATH='.'; .venv\Scripts\python -m pytest -q` | Passed with **11 tests**. One upstream `StarletteDeprecationWarning` was emitted by the test client stack. |
| API runtime health | `GET http://127.0.0.1:8000/health` | Returned `status: ok`, deterministic demo mode, and SQLite health. |
| Dashboard API flow | `GET /api/v1/dashboard` with `X-FieldSight-Workspace=org-solarvista` | Passed after fixing timezone handling in the dashboard KPI calculation. |
| Edge-agent help | `python agent.py --help` | Passed. CLI help rendered correctly. |
| Edge-agent end-to-end demo | `python agent.py run-demo-mission --device edge-03 --count 2 --api http://127.0.0.1:8000` | Passed. Two offline captures synchronized successfully and produced two deterministic findings. |
| Frontend lint | `npm run lint` | Passed. |
| Frontend type check | `npm run typecheck` | Passed. |
| Frontend production build | `npm run build` | Passed. Next.js generated all **24/24** static routes. |
| Frontend browser tests | `npm run test:e2e` | Passed with **4 Playwright tests** after tightening one strict-mode locator in the media route test. |
| Production web runtime | `npm run start` after `npm run build` | Passed after adding a local standalone start wrapper that copies static assets into the runtime bundle before launch. |
| Screenshot capture | `npm run capture:screens` | Passed. Real browser screenshots were captured into `docs/screenshots/` from the locally running seeded application and API docs. |

## Honest limitations

| Check | Actual outcome |
| --- | --- |
| Docker validation | Not completed because Docker is not installed in this environment (`docker` command unavailable). |
| External integrations | Not configured by design in this run. Deterministic local mode was used instead of live CMMS, ERP, GIS, Slack, email, weather, remote inference, object storage, or physical device providers. |

## Notes

- The frontend `package-lock.json` was regenerated from the public npm registry because the inherited lockfile referenced a private mirror URL that is not appropriate for a public GitHub repository.
- Browser screenshots use seeded synthetic data only. They do not represent customer data, production telemetry, or real inspection outputs.
