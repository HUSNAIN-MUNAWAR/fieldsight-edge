# Observability

`/health` and `/api/v1/operations/health` expose API, database, local storage, inference queue, edge-sync queue, worker-mode, and migration metadata. Request IDs are generated for each request and returned as `X-Request-ID`. Audit events connect important writes to actor, workspace, target, request ID, and structured metadata. Centralized logs, metrics, tracing, and error tracking remain deployment work.
