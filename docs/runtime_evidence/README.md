# Runtime evidence

Run from the repository root:

```bash
python scripts/generate_runtime_evidence.py
```

The script launches the actual FastAPI application in a temporary SQLite
database, logs in through the real auth route, switches `edge-03` offline,
creates three persisted captures, inspects the queue, synchronizes them, and
exports the PDF report. It writes:

- `edge-runtime-trace.json` and `.csv` — measured API state transitions;
- `edge-runtime-trace.mp4` and `edge-runtime-trace-poster.jpg` — an animation
  rendered from those responses;
- `fieldsight-runtime-report.pdf` — the real API report response;
- `summary.json` — counts, status codes, video metadata, and hashes.

The local path uses SQLite, synthetic capture bytes, and the explicit
`deterministic-demo` provider. It demonstrates persistence, queueing, sync,
reviewable findings, and reporting, but does not claim physical camera accuracy
or a deployed edge model.
