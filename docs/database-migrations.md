# Database migrations

Phase 2 establishes the persistent core with revision `20260707_01`. Phase 3 adds explicit governance/launch-control tables in `20260707_02`: watchlists, watchlist items, report schedules, dataset candidates, model evaluations, model deployments, and deletion requests. Verify with `PYTHONPATH=. alembic upgrade head` and `scripts/migration_status.py`. Production startup validates configuration but does not invoke metadata bootstrap. Backups and tested rollback procedures are required before production migration.
