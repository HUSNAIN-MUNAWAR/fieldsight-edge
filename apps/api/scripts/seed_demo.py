from app.database import Base, SessionLocal, engine
from app.seed import seed_demo_data
from app.seed_phase3 import seed_phase3_data

Base.metadata.create_all(bind=engine)
with SessionLocal() as session:
    seed_demo_data(session)
    seed_phase3_data(session)
print("FieldSight Edge Phase 3 demo data is ready (idempotent).")
