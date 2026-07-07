"""Idempotent Phase 3 launch-control seed records."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import (
    Membership,
    User,
    DatasetCandidate,
    DatasetVersion,
    Finding,
    ModelDeployment,
    ModelEvaluation,
    ModelVersion,
    ReportSchedule,
    Watchlist,
    WatchlistItem,
)

NOW = datetime(2026, 7, 7, 11, 0, tzinfo=timezone.utc)


def _ensure(db: Session, model: type, identity: str, **values: object) -> object:
    existing = db.get(model, identity)
    if existing:
        return existing
    return model(id=identity, created_at=NOW, updated_at=NOW, **values)


def seed_phase3_data(db: Session) -> None:
    # This function is safe to call after every local startup and after explicit seed runs.
    from .security import hash_secret
    db.add(_ensure(db, User, "usr-data-scientist-solar", email="scientist@solarvista.demo", name="Omar Siddiqui", password_hash=hash_secret("DemoPass123!"), is_platform_admin=False, active=True))
    db.add(_ensure(db, Membership, "mem-scientist-solar", user_id="usr-data-scientist-solar", organization_id="org-solarvista", role="Data Scientist", site_restrictions=[]))
    specs = [
        ("watch-critical-solar", "org-solarvista", "Critical assets", "Evidence-linked high-risk solar assets", "Risk"),
        ("watch-edge-atlas", "org-atlas", "Devices needing attention", "Offline queues and retry-safe sync issues", "Fleet"),
        ("watch-quality-meridian", "org-meridian", "Inspection quality risks", "Coverage and metadata follow-up", "Data Quality"),
    ]
    for ident, org, name, description, category in specs:
        db.add(_ensure(db, Watchlist, ident, organization_id=org, name=name, description=description, category=category, created_by="usr-platform"))
    item_specs = [
        ("watchitem-solar", "org-solarvista", "watch-critical-solar", "asset", "asset-001", "Prioritize evidence verification"),
        ("watchitem-atlas", "org-atlas", "watch-edge-atlas", "device", "edge-03", "Offline queue retained for demo"),
    ]
    for ident, org, watch, entity_type, entity_id, note in item_specs:
        db.add(_ensure(db, WatchlistItem, ident, organization_id=org, watchlist_id=watch, entity_type=entity_type, entity_id=entity_id, note=note))

    schedule_specs = [
        ("schedule-solar-weekly", "org-solarvista", "prj-solar-alpha", "Weekly Site Risk Brief", "executive", "weekly"),
        ("schedule-atlas-daily", "org-atlas", "prj-utility-north", "Daily Fleet Health Brief", "fleet", "daily"),
    ]
    for ident, org, project, name, template, frequency in schedule_specs:
        db.add(_ensure(db, ReportSchedule, ident, organization_id=org, project_id=project, name=name, template=template, frequency=frequency, scope={"synthetic": True}, enabled=True, last_run_at=None))

    # Dataset candidates attach to real seeded findings only when they exist.
    finding = db.scalar(select(Finding).where(Finding.organization_id == "org-solarvista").limit(1))
    if finding:
        db.add(_ensure(db, DatasetCandidate, "candidate-seed-solar", organization_id="org-solarvista", finding_id=finding.id, state="Candidate", rationale="Synthetic corrected example for workflow validation", reviewer_id="usr-reviewer-solar"))

    model = db.scalar(select(ModelVersion).where(or_(ModelVersion.organization_id == "org-solarvista", ModelVersion.organization_id.is_(None))).limit(1))
    dataset = db.scalar(select(DatasetVersion).where(DatasetVersion.organization_id == "org-solarvista").limit(1))
    if model and dataset:
        evaluation = db.scalar(select(ModelEvaluation).where(ModelEvaluation.organization_id == "org-solarvista", ModelEvaluation.model_version_id == model.id, ModelEvaluation.dataset_version_id == dataset.id))
        if not evaluation:
            db.add(_ensure(db, ModelEvaluation, "eval-seed-solar", organization_id="org-solarvista", model_version_id=model.id, dataset_version_id=dataset.id, state="Completed", metrics={"precision_proxy": 0.91, "recall_proxy": 0.88, "f1_proxy": 0.895, "latency_ms_p95": 138, "synthetic": True}, recommendation="Governed review required", synthetic=True))
        deployment = db.scalar(select(ModelDeployment).where(ModelDeployment.organization_id == "org-solarvista", ModelDeployment.model_version_id == model.id, ModelDeployment.target == "device-group:solar-east"))
        if not deployment:
            db.add(_ensure(db, ModelDeployment, "deploy-seed-solar", organization_id="org-solarvista", model_version_id=model.id, target="device-group:solar-east", state="Deployed", approval_history=[{"at": NOW.isoformat(), "by": "Husnain Demo", "decision": "seeded simulation"}], rollout={"simulation": True, "device_binary_updated": False}))
    db.commit()
