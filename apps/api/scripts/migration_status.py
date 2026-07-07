from __future__ import annotations
from sqlalchemy import text
from app.database import engine

with engine.connect() as connection:
    version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
print({"database": engine.url.get_backend_name(), "alembic_head": version or "unversioned"})
