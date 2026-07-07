# Architecture

See the README architecture graph for the code-accurate topology. The monorepo has: Next.js console; FastAPI API; SQLAlchemy records; explicit Alembic revisions; local storage; deterministic inference; edge-agent simulator; PDFs; audit/health endpoints. SQLite and coordinate fallback keep local demo usable. PostgreSQL/PostGIS/Redis/S3/provider integrations are deployment boundaries.
