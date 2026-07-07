# Media ingestion

`POST /api/v1/media/intake` accepts local image upload and optional asset/site/mission references. It stores original bytes locally, validates evidence, detects checksum duplicates, records metadata/quality state, creates an audit event, then runs deterministic inference. Batch/S3/drone import are documented extension paths.
