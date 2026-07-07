# Testing

Backend tests exercise login, legacy Phase 1 compatibility, tenant isolation, media duplicate detection, deterministic inference, offline capture/sync, risk/change flow, review-to-work-order, approval, and report export. Phase 3 tests add migrations, watchlists, model release, report schedules, API-key revocation, lifecycle transitions, and evidence-package boundaries. Browser testing needs installed Playwright browsers and a running API/web server.

## CI structure

The GitHub workflow runs migration/seed checks, Ruff, backend tests, ESLint, TypeScript, production build, and a best-effort browser/accessibility boundary. Browser jobs are deliberately `continue-on-error` because their dependencies require browser installation and service-process availability. A green local lint/type/test result is not a substitute for production monitoring.
