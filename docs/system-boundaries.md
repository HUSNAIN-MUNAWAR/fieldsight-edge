# System boundaries

FieldSight Edge runs deterministically with FastAPI, SQLite, local filesystem storage, and the CPU-first edge simulator. PostgreSQL, PostGIS, Redis workers, S3-compatible object storage, map providers, model runtimes, CMMS/ERP/GIS, Slack/email/weather, and real device provisioning are deployment boundaries. No adapter is reported as live unless it is configured and its health is observable.
