"""phase 3 launch hardening records

Revision ID: 20260707_02
Revises: 20260707_01
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa

revision = "20260707_02"
down_revision = "20260707_01"
branch_labels = None
depends_on = None


def timestamp_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "watchlists",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.String(length=64), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=80), nullable=False, server_default="Operational"),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        *timestamp_columns(),
        sa.UniqueConstraint("organization_id", "name", name="uq_watchlist_org_name"),
    )
    op.create_index("ix_watchlists_org", "watchlists", ["organization_id"])
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.String(length=64), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("watchlist_id", sa.String(length=64), sa.ForeignKey("watchlists.id"), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        *timestamp_columns(),
        sa.UniqueConstraint("organization_id", "watchlist_id", "entity_type", "entity_id", name="uq_watchlist_item"),
    )
    op.create_index("ix_watchlist_items_org", "watchlist_items", ["organization_id"])
    op.create_table(
        "report_schedules",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.String(length=64), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.String(length=64), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("template", sa.String(length=100), nullable=False, server_default="executive"),
        sa.Column("frequency", sa.String(length=32), nullable=False, server_default="weekly"),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.UniqueConstraint("organization_id", "name", name="uq_report_schedule_org_name"),
    )
    op.create_index("ix_report_schedules_org", "report_schedules", ["organization_id"])
    op.create_table(
        "dataset_candidates",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.String(length=64), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("finding_id", sa.String(length=64), sa.ForeignKey("findings.id"), nullable=False),
        sa.Column("state", sa.String(length=48), nullable=False, server_default="Candidate"),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("reviewer_id", sa.String(length=64), nullable=True),
        *timestamp_columns(),
        sa.UniqueConstraint("organization_id", "finding_id", name="uq_dataset_candidate_finding"),
    )
    op.create_index("ix_dataset_candidates_org", "dataset_candidates", ["organization_id"])
    op.create_table(
        "model_evaluations",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.String(length=64), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("model_version_id", sa.String(length=64), sa.ForeignKey("model_versions.id"), nullable=False),
        sa.Column("dataset_version_id", sa.String(length=64), sa.ForeignKey("dataset_versions.id"), nullable=False),
        sa.Column("state", sa.String(length=48), nullable=False, server_default="Completed"),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("recommendation", sa.String(length=120), nullable=False, server_default="Review required"),
        sa.Column("synthetic", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamp_columns(),
        sa.UniqueConstraint("organization_id", "model_version_id", "dataset_version_id", name="uq_model_eval_scope"),
    )
    op.create_index("ix_model_evaluations_org", "model_evaluations", ["organization_id"])
    op.create_table(
        "model_deployments",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.String(length=64), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("model_version_id", sa.String(length=64), sa.ForeignKey("model_versions.id"), nullable=False),
        sa.Column("target", sa.String(length=160), nullable=False),
        sa.Column("state", sa.String(length=48), nullable=False, server_default="Staged"),
        sa.Column("approval_history", sa.JSON(), nullable=False),
        sa.Column("rollout", sa.JSON(), nullable=False),
        *timestamp_columns(),
        sa.UniqueConstraint("organization_id", "model_version_id", "target", name="uq_model_deploy_target"),
    )
    op.create_index("ix_model_deployments_org", "model_deployments", ["organization_id"])
    op.create_table(
        "deletion_requests",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.String(length=64), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("request_key", sa.String(length=120), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("state", sa.String(length=48), nullable=False, server_default="Requested"),
        sa.Column("requested_by", sa.String(length=64), nullable=False),
        *timestamp_columns(),
        sa.UniqueConstraint("organization_id", "request_key", name="uq_deletion_request_key"),
    )
    op.create_index("ix_deletion_requests_org", "deletion_requests", ["organization_id"])


def downgrade() -> None:
    for table in ("deletion_requests", "model_deployments", "model_evaluations", "dataset_candidates", "report_schedules", "watchlist_items", "watchlists"):
        op.drop_table(table)
