"""Worker boundary for deployment.

The local deterministic demo executes jobs synchronously for zero-dependency usability.
Deployments can run this process with Redis/Celery/RQ or another queue implementation and
claim queued InferenceJob records without changing the API contract.
"""

from __future__ import annotations
import time
from .database import SessionLocal
from .models import InferenceJob


def main() -> None:
    print("FieldSight worker boundary started. Demo mode does not claim external queue execution.")
    while True:
        with SessionLocal() as db:
            queued = db.query(InferenceJob).filter(InferenceJob.state.in_(["Queued", "Retrying"])).count()
        print(f"worker boundary heartbeat: {queued} durable job(s) awaiting a configured provider")
        time.sleep(30)


if __name__ == "__main__":
    main()
