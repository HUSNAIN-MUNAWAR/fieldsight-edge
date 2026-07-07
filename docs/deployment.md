# Deployment

Local mode uses SQLite and deterministic inference. Production mode requires `FIELDSIGHT_ENV=production`, `FIELDSIGHT_DEMO_MODE=false`, PostgreSQL `DATABASE_URL`, a non-demo secret, and explicit trusted origins. Run Alembic before application startup. Deploy FastAPI behind TLS/reverse proxy, Next.js separately, worker and Redis separately, and configure managed object storage. Do not treat Docker Compose as proof of production readiness.
