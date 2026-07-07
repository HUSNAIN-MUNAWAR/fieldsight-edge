# Edge sync protocol

Sync jobs are organization-scoped and idempotency-keyed. Capture records can remain queued offline; reconnect triggers upload, validation, durable media records, deterministic inference, and acknowledgement. Corrupt files and missing metadata remain visible as failures/warnings rather than being silently accepted. Resumable multipart upload is a production boundary.
