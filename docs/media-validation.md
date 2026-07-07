# Media validation

Media intake checks content policy, extension, file size, checksum uniqueness, dimensions, basic quality proxies, missing metadata warnings, and idempotency keys. Original media is stored by `storage_key`; validation does not silently alter evidence. Duplicate checks are organization scoped. See `media_lineage` and evidence-package export routes for traceability.
