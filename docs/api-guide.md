# API guide

The public boundary is `/api/v1/`. Use a Bearer access token from login plus `X-FieldSight-Workspace`. Major write paths create audit events and return request IDs in response headers. Media intake accepts `Idempotency-Key`; edge sync and checksums avoid duplicate handling. Use pagination/filtering boundaries where lists grow; local demo lists are intentionally small. API keys are persisted, scoped, expiring, and revocable records; do not expose their secret values after creation.

Core groups: auth, workspaces, dashboard/map, missions, media/lineage, inference, findings/review, work orders, assets/risk/changes, devices/sync, models/datasets/deployments, alerts/watchlists, reports/schedules, governance, search, assistant, operations health.
