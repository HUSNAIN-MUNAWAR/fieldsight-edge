"""phase 2 persistent multi-tenant core

Revision ID: 20260707_01
Revises:
Create Date: 2026-07-07
"""

from alembic import op
from app.database import Base
from app import models  # noqa: F401

revision = "20260707_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Metadata-driven initial migration keeps the schema portable between SQLite demo and PostgreSQL deployment.
    Base.metadata.create_all(
        bind=op.get_bind(),
        tables=[
            Base.metadata.tables[name]
            for name in (
                "organizations", "users", "memberships", "projects", "sites", "assets", "missions",
                "media_files", "model_versions", "dataset_versions", "inference_jobs", "findings", "defects",
                "work_orders", "devices", "sync_jobs", "asset_risk_snapshots", "alerts", "reports",
                "audit_events", "api_keys", "webhook_deliveries", "token_sessions",
            )
        ],
    )


def downgrade() -> None:
    Base.metadata.drop_all(
        bind=op.get_bind(),
        tables=[Base.metadata.tables[name] for name in list(Base.metadata.tables) if name not in {
            "watchlists", "watchlist_items", "report_schedules", "dataset_candidates", "model_evaluations", "model_deployments", "deletion_requests"
        }],
    )
