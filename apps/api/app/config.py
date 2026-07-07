"""Runtime configuration and startup safety checks for FieldSight Edge."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("FIELDSIGHT_ENV", "development").lower()
    database_url: str = os.getenv("DATABASE_URL", "")
    demo_mode: bool = os.getenv("FIELDSIGHT_DEMO_MODE", "true").lower() == "true"
    trusted_origins: tuple[str, ...] = tuple(
        x.strip() for x in os.getenv("FIELDSIGHT_TRUSTED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if x.strip()
    )
    secret: str = os.getenv("FIELDSIGHT_APP_SECRET", "fieldsight-local-demo-only")
    worker_mode: str = os.getenv("FIELDSIGHT_WORKER_MODE", "inline")


def validate_startup(settings: Settings) -> None:
    """Fail fast only for explicit production mode; local deterministic mode remains frictionless."""
    if settings.environment != "production":
        return
    if settings.demo_mode:
        raise RuntimeError("Production startup requires FIELDSIGHT_DEMO_MODE=false.")
    if not settings.database_url.startswith("postgresql"):
        raise RuntimeError("Production startup requires a PostgreSQL DATABASE_URL; SQLite is local-only.")
    if settings.secret in {"", "fieldsight-local-demo-only", "changeme", "demo"}:
        raise RuntimeError("Production startup requires a non-demo FIELDSIGHT_APP_SECRET.")
    if not settings.trusted_origins:
        raise RuntimeError("Production startup requires explicit trusted origins.")
