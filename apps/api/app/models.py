from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Organization(Base, Timestamped):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    industry: Mapped[str] = mapped_column(String(120), nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class User(Base, Timestamped):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Membership(Base, Timestamped):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="uq_membership"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    site_restrictions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class Project(Base, Timestamped):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    industry: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="Active")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Site(Base, Timestamped):
    __tablename__ = "sites"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    boundary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    coverage_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Asset(Base, Timestamped):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(120), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    criticality: Mapped[str] = mapped_column(String(32), default="standard", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Mission(Base, Timestamped):
    __tablename__ = "missions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    mission_type: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(48), nullable=False, default="Draft")
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    assigned_operator: Mapped[str | None] = mapped_column(String(120), nullable=True)
    assigned_device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    due_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    zones: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    checklist: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class MediaFile(Base, Timestamped):
    __tablename__ = "media_files"
    __table_args__ = (UniqueConstraint("organization_id", "checksum", name="uq_media_checksum_org"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True, index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    mission_id: Mapped[str | None] = mapped_column(ForeignKey("missions.id"), nullable=True, index=True)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(160), nullable=False)
    validation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    quality: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ModelVersion(Base, Timestamped):
    __tablename__ = "model_versions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(48), nullable=False)
    model_family: Mapped[str] = mapped_column(String(100), nullable=False)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    runtime: Mapped[str] = mapped_column(String(100), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    model_card: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class DatasetVersion(Base, Timestamped):
    __tablename__ = "dataset_versions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source: Mapped[str] = mapped_column(String(160), nullable=False)
    image_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    annotation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class InferenceJob(Base, Timestamped):
    __tablename__ = "inference_jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    media_id: Mapped[str] = mapped_column(ForeignKey("media_files.id"), nullable=False, index=True)
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, default="deterministic-demo")
    state: Mapped[str] = mapped_column(String(48), nullable=False, default="Queued")
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Finding(Base, Timestamped):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    media_id: Mapped[str] = mapped_column(ForeignKey("media_files.id"), nullable=False, index=True)
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True, index=True)
    inference_job_id: Mapped[str | None] = mapped_column(ForeignKey("inference_jobs.id"), nullable=True)
    defect_class: Mapped[str] = mapped_column(String(100), nullable=False)
    defect_subclass: Mapped[str | None] = mapped_column(String(100), nullable=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    review_state: Mapped[str] = mapped_column(String(48), nullable=False, default="pending")
    bbox: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    mask: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    quality_warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer_decision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_candidate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    human_override: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Defect(Base, Timestamped):
    __tablename__ = "defects"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id"), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(48), nullable=False, default="Verified")
    severity: Mapped[str] = mapped_column(String(32), nullable=False)


class WorkOrder(Base, Timestamped):
    __tablename__ = "work_orders"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    finding_id: Mapped[str | None] = mapped_column(ForeignKey("findings.id"), nullable=True, unique=True)
    defect_id: Mapped[str | None] = mapped_column(ForeignKey("defects.id"), nullable=True)
    mission_id: Mapped[str | None] = mapped_column(ForeignKey("missions.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="Draft")
    assignee: Mapped[str | None] = mapped_column(String(120), nullable=True)
    due_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    estimated_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checklist: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    resolution_evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    approval_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)


class Device(Base, Timestamped):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    device_type: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(48), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    health: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SyncJob(Base, Timestamped):
    __tablename__ = "sync_jobs"
    __table_args__ = (UniqueConstraint("organization_id", "idempotency_key", name="uq_sync_idempotency"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    media_id: Mapped[str | None] = mapped_column(ForeignKey("media_files.id"), nullable=True)
    state: Mapped[str] = mapped_column(String(48), nullable=False, default="Queued offline")
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AssetRiskSnapshot(Base, Timestamped):
    __tablename__ = "asset_risk_snapshots"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    drivers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    overridden_by: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Alert(Base, Timestamped):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(48), nullable=False, default="Open")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Report(Base, Timestamped):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(48), nullable=False, default="Draft")
    template: Mapped[str] = mapped_column(String(80), nullable=False, default="executive")
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    export_key: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(160), nullable=False)
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class APIKey(Base, Timestamped):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WebhookDelivery(Base, Timestamped):
    __tablename__ = "webhook_deliveries"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    state: Mapped[str] = mapped_column(String(48), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class TokenSession(Base, Timestamped):
    __tablename__ = "token_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    refresh_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Watchlist(Base, Timestamped):
    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_watchlist_org_name"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="Operational", nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)


class WatchlistItem(Base, Timestamped):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("organization_id", "watchlist_id", "entity_type", "entity_id", name="uq_watchlist_item"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    watchlist_id: Mapped[str] = mapped_column(ForeignKey("watchlists.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)


class ReportSchedule(Base, Timestamped):
    __tablename__ = "report_schedules"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_report_schedule_org_name"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    template: Mapped[str] = mapped_column(String(100), nullable=False, default="executive")
    frequency: Mapped[str] = mapped_column(String(32), nullable=False, default="weekly")
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DatasetCandidate(Base, Timestamped):
    __tablename__ = "dataset_candidates"
    __table_args__ = (UniqueConstraint("organization_id", "finding_id", name="uq_dataset_candidate_finding"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id"), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(48), nullable=False, default="Candidate")
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ModelEvaluation(Base, Timestamped):
    __tablename__ = "model_evaluations"
    __table_args__ = (UniqueConstraint("organization_id", "model_version_id", "dataset_version_id", name="uq_model_eval_scope"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"), nullable=False, index=True)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(48), nullable=False, default="Completed")
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(120), default="Review required", nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ModelDeployment(Base, Timestamped):
    __tablename__ = "model_deployments"
    __table_args__ = (UniqueConstraint("organization_id", "model_version_id", "target", name="uq_model_deploy_target"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"), nullable=False, index=True)
    target: Mapped[str] = mapped_column(String(160), nullable=False)
    state: Mapped[str] = mapped_column(String(48), nullable=False, default="Staged")
    approval_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    rollout: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class DeletionRequest(Base, Timestamped):
    __tablename__ = "deletion_requests"
    __table_args__ = (UniqueConstraint("organization_id", "request_key", name="uq_deletion_request_key"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    request_key: Mapped[str] = mapped_column(String(120), nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    state: Mapped[str] = mapped_column(String(48), nullable=False, default="Requested")
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
