from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / ".data" / "fieldsight.db"
DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine_options = {"future": True, "pool_pre_ping": True, "connect_args": connect_args}
if not DATABASE_URL.startswith("sqlite"):
    engine_options.update({"pool_size": int(os.getenv("DB_POOL_SIZE", "5")), "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10"))})
engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def database_status() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "dialect": engine.url.get_backend_name()}
    except Exception as exc:  # pragma: no cover - defensive health boundary
        return {"status": "error", "dialect": engine.url.get_backend_name(), "detail": str(exc)[:180]}


def get_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
