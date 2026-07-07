# Inference pipeline

Inference job records contain provider, model version, state, idempotency key, duration, error, and profile. Deterministic local inference is the default and fully working. YOLO-compatible, ONNX Runtime, remote, edge, and batch adapters are interfaces/boundaries; no model weights are downloaded or claimed active. Critical findings require human confirmation before work-order creation.
