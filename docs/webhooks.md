# Webhooks

Webhook delivery records are persisted for governance and integration boundaries. Event examples: `media.uploaded`, `inference.completed`, `finding.reviewed`, `work_order.created`, `work_order.completed`, `device.sync_failed`, `report.generated`, and `model.deployment_changed`. Production configuration should add signed payloads, target allowlists, retry workers, dead-letter queues, payload redaction, per-workspace secrets, and delivery monitoring.
