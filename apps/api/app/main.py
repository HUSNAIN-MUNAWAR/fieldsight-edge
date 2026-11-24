from __future__ import annotations

import io
from contextlib import asynccontextmanager
from datetime import timedelta, timezone
from typing import Any, Annotated

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from .config import Settings, validate_startup
from .database import Base, SessionLocal, database_status, engine, get_session
from .models import (
    APIKey,
    Alert,
    Asset,
    AssetRiskSnapshot,
    AuditEvent,
    DatasetVersion,
    Device,
    Finding,
    InferenceJob,
    MediaFile,
    Membership,
    Mission,
    ModelVersion,
    Organization,
    Project,
    Report,
    Site,
    SyncJob,
    TokenSession,
    User,
    WorkOrder,
    Defect,
    WebhookDelivery,
    Watchlist,
    WatchlistItem,
    ReportSchedule,
    DatasetCandidate,
    ModelEvaluation,
    ModelDeployment,
    DeletionRequest,
)
from .security import expires_in, hash_secret, issue_token, make_id, now, token_hash, verify_secret
from .seed import seed_demo_data
from .seed_phase3 import seed_phase3_data
from .services.inference import DeterministicDemoProvider, TAXONOMY
from .services.quality import assess_media
from .services.risk import calculate_risk
from .storage import LocalStorage, checksum

SETTINGS = Settings()

DEMO_ORG = "org-solarvista"
DEMO_USER = "usr-platform"
storage = LocalStorage()

# TestClient instances created without a context manager do not execute lifespan.
# Keep deterministic local/demo state available for that supported developer workflow;
# explicit Alembic migration remains required in production mode.
if SETTINGS.environment != "production":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as _bootstrap_db:
        seed_demo_data(_bootstrap_db)
        seed_phase3_data(_bootstrap_db)


def aware_datetime(value):
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_startup(SETTINGS)
    # Local deterministic mode keeps the portfolio runnable without Docker.
    # Production deployments must run explicit Alembic migrations before startup.
    if SETTINGS.environment != "production":
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
        seed_phase3_data(db)
    yield


app = FastAPI(
    title="FieldSight Edge API",
    version="0.3.0",
    description="Evidence-first multi-tenant industrial inspection API. Deterministic local mode remains the CPU-first default.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(SETTINGS.trusted_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Any) -> Response:
    request.state.request_id = request.headers.get("X-Request-ID") or make_id("req")
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"
    return response


class LoginRequest(BaseModel):
    email: str
    password: str


class ReviewRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject|uncertain|escalate)$")
    severity: str | None = Field(default=None, pattern="^(critical|high|medium|low)$")
    defect_type: str | None = None
    note: str = ""
    training_candidate: bool = False


class WorkOrderRequest(BaseModel):
    title: str | None = None
    assignee: str | None = "Unassigned"
    due_date: str | None = None
    estimated_cost: int | None = None


class MissionRequest(BaseModel):
    name: str
    project_id: str
    site_id: str
    mission_type: str = "Routine inspection"
    priority: str = "normal"
    assigned_operator: str | None = None
    assigned_device_id: str | None = None
    due_date: str | None = None
    zones: list[str] = []
    offline_enabled: bool = True


class DeviceModeRequest(BaseModel):
    mode: str = Field(pattern="^(online|offline|syncing|degraded)$")


class ReportRequest(BaseModel):
    project_id: str = "prj-solar-alpha"
    title: str = "Solar Farm Alpha — Inspection Report"
    template: str = "executive"


class AssistantRequest(BaseModel):
    question: str
    mode: str = "Executive Brief"


class ApiKeyRequest(BaseModel):
    name: str
    scopes: list[str] = ["projects:read", "media:write"]
    expires_days: int = 90


class Context(BaseModel):
    user_id: str
    user_name: str
    organization_id: str
    role: str
    platform_admin: bool = False


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "Platform Admin": {"*"},
    "Organization Admin": {"*"},
    "Inspection Manager": {"mission:write", "review:write", "workorder:write", "report:write", "read"},
    "Field Operator": {"mission:read", "media:write", "device:write", "read"},
    "Reviewer": {"review:write", "read"},
    "Maintenance Coordinator": {"workorder:write", "read"},
    "Data Scientist": {"model:write", "dataset:write", "read"},
    "Viewer": {"read"},
}


def get_context(
    request: Request,
    db: Session = Depends(get_session),
    authorization: Annotated[str | None, Header()] = None,
    workspace: Annotated[str | None, Header(alias="X-FieldSight-Workspace")] = None,
) -> Context:
    user = db.get(User, DEMO_USER)
    if authorization and authorization.lower().startswith("bearer "):
        session = db.scalar(
            select(TokenSession).where(
                TokenSession.token_hash == token_hash(authorization.split(" ", 1)[1]),
                TokenSession.revoked_at.is_(None),
            )
        )
        session_expiry = (
            session.expires_at.replace(tzinfo=timezone.utc)
            if session and session.expires_at.tzinfo is None
            else (session.expires_at if session else None)
        )
        if not session or session_expiry < now():
            raise HTTPException(status_code=401, detail="Token is expired or invalid.")
        user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="No active user context.")
    org_id = workspace or DEMO_ORG
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.organization_id == org_id)
    )
    if not user.is_platform_admin and not membership:
        raise HTTPException(status_code=403, detail="Workspace access is not granted for this user.")
    role = membership.role if membership else "Platform Admin"
    if not db.get(Organization, org_id):
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return Context(
        user_id=user.id,
        user_name=user.name,
        organization_id=org_id,
        role=role,
        platform_admin=user.is_platform_admin,
    )


def require(permission: str):
    def dependency(ctx: Context = Depends(get_context)) -> Context:
        allowed = ROLE_PERMISSIONS.get(ctx.role, set())
        if "*" not in allowed and permission not in allowed:
            raise HTTPException(status_code=403, detail=f"Role {ctx.role} cannot perform {permission}.")
        return ctx

    return dependency


def require_approval(ctx: Context = Depends(get_context)) -> Context:
    if ctx.role not in {"Platform Admin", "Organization Admin", "Inspection Manager"}:
        raise HTTPException(status_code=403, detail="This approval requires an Organization Admin or Inspection Manager.")
    return ctx


def require_model_approval(ctx: Context = Depends(get_context)) -> Context:
    if ctx.role not in {"Platform Admin", "Organization Admin"}:
        raise HTTPException(status_code=403, detail="Model deployment approval requires an Organization Admin.")
    return ctx


def org_item(db: Session, model: type, item_id: str, ctx: Context) -> Any:
    item = db.get(model, item_id)
    if not item or getattr(item, "organization_id", ctx.organization_id) != ctx.organization_id:
        # Deliberately return 404 to avoid leaking another tenant's entity.
        raise HTTPException(status_code=404, detail="Record not found in the active workspace.")
    return item


def audit(
    db: Session,
    ctx: Context,
    request: Request | None,
    action: str,
    target_type: str,
    target_id: str,
    **metadata: Any,
) -> None:
    db.add(
        AuditEvent(
            id=make_id("audit"),
            organization_id=ctx.organization_id,
            occurred_at=now(),
            actor_id=ctx.user_id,
            actor_name=ctx.user_name,
            action=action,
            target_type=target_type,
            target_id=target_id,
            request_id=getattr(getattr(request, "state", None), "request_id", None),
            metadata_json=metadata,
        )
    )


def compact_org(org: Organization) -> dict[str, Any]:
    return {"id": org.id, "name": org.name, "slug": org.slug, "industry": org.industry}


def asset_out(asset: Asset, db: Session) -> dict[str, Any]:
    snapshot = db.scalar(
        select(AssetRiskSnapshot)
        .where(AssetRiskSnapshot.asset_id == asset.id)
        .order_by(desc(AssetRiskSnapshot.created_at))
    )
    return {
        "id": asset.id,
        "name": asset.name,
        "asset_type": asset.asset_type,
        "site_id": asset.site_id,
        "lat": asset.latitude,
        "lng": asset.longitude,
        "criticality": asset.criticality,
        "risk_score": snapshot.score if snapshot else 0,
        "risk_level": snapshot.level if snapshot else "Unknown",
        "tags": asset.tags,
    }


def media_out(media: MediaFile) -> dict[str, Any]:
    return {
        "id": media.id,
        "asset_id": media.asset_id,
        "site_id": media.site_id,
        "mission_id": media.mission_id,
        "filename": media.filename,
        "captured_at": media.captured_at.isoformat(),
        "source": media.source,
        "lat": media.latitude,
        "lng": media.longitude,
        "width": media.width,
        "height": media.height,
        "checksum": media.checksum,
        "validation": media.validation,
        "quality": media.quality,
    }


def finding_out(f: Finding, db: Session) -> dict[str, Any]:
    media = db.get(MediaFile, f.media_id)
    asset = db.get(Asset, f.asset_id) if f.asset_id else None
    work = db.scalar(select(WorkOrder).where(WorkOrder.finding_id == f.id))
    label = TAXONOMY.get(f.defect_class, {}).get("label", f.defect_class.replace("_", " ").title())
    return {
        "id": f.id,
        "media_id": f.media_id,
        "asset_id": f.asset_id,
        "class_key": f.defect_class,
        "label": label,
        "severity": f.severity,
        "confidence": f.confidence,
        "review_state": f.review_state,
        "model_version": db.get(InferenceJob, f.inference_job_id).model_version_id
        if f.inference_job_id and db.get(InferenceJob, f.inference_job_id)
        else "vision-solar-1.4.2",
        "bbox": f.bbox,
        "mask": f.mask,
        "created_at": f.created_at.isoformat(),
        "review_note": f.reviewer_note or "",
        "reviewed_by": f.reviewed_by,
        "training_candidate": f.training_candidate,
        "quality_warnings": f.quality_warnings,
        "media": media_out(media) if media else None,
        "asset": asset_out(asset, db) if asset else None,
        "work_order": work_order_out(work) if work else None,
    }


def work_order_out(w: WorkOrder) -> dict[str, Any]:
    return {
        "id": w.id,
        "title": w.title,
        "finding_id": w.finding_id,
        "asset_id": w.asset_id,
        "severity": w.severity,
        "priority": w.priority,
        "status": w.status,
        "assignee": w.assignee,
        "sla_due": w.due_date,
        "estimated_cost": w.estimated_cost,
        "checklist": w.checklist,
        "resolution_evidence": w.resolution_evidence,
        "approval_history": w.approval_history,
        "created_at": w.created_at.isoformat(),
    }


def device_out(d: Device, db: Session) -> dict[str, Any]:
    queued = (
        db.scalar(
            select(func.count())
            .select_from(SyncJob)
            .where(SyncJob.device_id == d.id, SyncJob.state != "Synchronized")
        )
        or 0
    )
    h = d.health or {}
    return {
        "id": d.id,
        "name": d.name,
        "site": db.get(Site, d.site_id).name if d.site_id and db.get(Site, d.site_id) else "Unassigned",
        "state": d.state,
        "type": d.device_type,
        "battery": h.get("battery", 0),
        "cpu": h.get("cpu", 0),
        "temp": h.get("temperature", 0),
        "storage": h.get("storage", 0),
        "network_quality": h.get("network_quality", "unknown"),
        "last_sync": d.last_seen_at.isoformat() if d.last_seen_at else "never",
        "model": d.model_version,
        "pending": queued,
        "failed_sync": h.get("failed_sync", 0),
        "health": h,
    }


def project_out(p: Project, db: Session) -> dict[str, Any]:
    sites = db.scalars(select(Site).where(Site.project_id == p.id)).all()
    return {
        "id": p.id,
        "name": p.name,
        "industry": p.industry,
        "status": p.status,
        "site_count": len(sites),
        "coverage": round(sum(x.coverage_percent for x in sites) / len(sites)) if sites else 0,
    }


def recompute_risk(db: Session, asset: Asset, ctx: Context) -> AssetRiskSnapshot:
    findings = db.scalars(
        select(Finding).where(Finding.asset_id == asset.id, Finding.review_state != "rejected")
    ).all()
    open_orders = (
        db.scalar(
            select(func.count())
            .select_from(WorkOrder)
            .where(WorkOrder.asset_id == asset.id, WorkOrder.status.notin_(["Verified", "Cancelled"]))
        )
        or 0
    )
    latest_media = db.scalar(
        select(MediaFile).where(MediaFile.asset_id == asset.id).order_by(desc(MediaFile.captured_at))
    )
    captured_at = (
        latest_media.captured_at.replace(tzinfo=timezone.utc)
        if latest_media and latest_media.captured_at.tzinfo is None
        else (latest_media.captured_at if latest_media else None)
    )
    freshness = (now() - captured_at).days if captured_at else 365
    quality_warning = bool(latest_media and (latest_media.quality or {}).get("warnings"))
    score, level, drivers = calculate_risk(findings, open_orders, freshness, quality_warning)
    snapshot = AssetRiskSnapshot(
        id=make_id("risk"),
        organization_id=ctx.organization_id,
        asset_id=asset.id,
        score=score,
        level=level,
        drivers=drivers,
        overridden_by=None,
        created_at=now(),
        updated_at=now(),
    )
    db.add(snapshot)
    return snapshot


def create_alert(
    db: Session,
    ctx: Context,
    category: str,
    severity: str,
    title: str,
    entity_type: str,
    entity_id: str,
    **detail: Any,
) -> Alert:
    alert = Alert(
        id=make_id("alert"),
        organization_id=ctx.organization_id,
        category=category,
        severity=severity,
        state="Open",
        title=title,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
        created_at=now(),
        updated_at=now(),
    )
    db.add(alert)
    return alert


def run_deterministic_inference(
    db: Session, ctx: Context, media: MediaFile, request: Request | None, idempotency_key: str | None = None
) -> Finding:
    key = idempotency_key or f"infer:{media.id}:vision-solar-1.4.2"
    existing_job = db.scalar(
        select(InferenceJob).where(
            InferenceJob.organization_id == ctx.organization_id, InferenceJob.idempotency_key == key
        )
    )
    if existing_job:
        existing_finding = db.scalar(select(Finding).where(Finding.inference_job_id == existing_job.id))
        if existing_finding:
            return existing_finding
    model = db.get(ModelVersion, "model-1.4.2")
    job = InferenceJob(
        id=make_id("job"),
        organization_id=ctx.organization_id,
        media_id=media.id,
        model_version_id=model.id,
        provider="deterministic-demo",
        state="Running",
        idempotency_key=key,
        duration_ms=None,
        error=None,
        profile={"confidence_policy": "human-confirmation-for-critical"},
        created_at=now(),
        updated_at=now(),
    )
    db.add(job)
    db.flush()
    try:
        media_bytes = storage.get(media.storage_key)
    except FileNotFoundError:
        media_bytes = None
    result = DeterministicDemoProvider().run(media.id, media.quality, content=media_bytes)
    review_state = (
        "pending" if result.severity == "critical" or result.confidence < 0.82 else "auto-accepted"
    )
    if result.confidence < 0.68:
        review_state = "uncertain"
    job.state = "Needs review" if review_state in {"pending", "uncertain"} else "Completed"
    job.duration_ms = result.duration_ms
    job.updated_at = now()
    finding = Finding(
        id=make_id("find"),
        organization_id=ctx.organization_id,
        media_id=media.id,
        asset_id=media.asset_id,
        inference_job_id=job.id,
        defect_class=result.defect_class,
        defect_subclass=None,
        severity=result.severity,
        confidence=result.confidence,
        review_state=review_state,
        bbox=result.bbox,
        mask=result.mask,
        quality_warnings=result.quality_warnings,
        reviewed_by=None,
        reviewer_decision=None,
        reviewer_note=None,
        training_candidate=False,
        human_override={},
        created_at=now(),
        updated_at=now(),
    )
    db.add(finding)
    if media.asset_id:
        asset = db.get(Asset, media.asset_id)
        if asset:
            recompute_risk(db, asset, ctx)
    if result.severity == "critical":
        create_alert(
            db,
            ctx,
            "critical_defect",
            "critical",
            f"Critical {result.label.lower()} requires human confirmation",
            "finding",
            finding.id,
            confidence=result.confidence,
        )
    audit(
        db,
        ctx,
        request,
        "Completed deterministic inference",
        "finding",
        finding.id,
        provider="deterministic-demo",
        duration_ms=result.duration_ms,
    )
    return finding


@app.get("/health")
def health(db: Session = Depends(get_session)) -> dict[str, Any]:
    return {
        "status": "ok",
        "mode": "persistent-deterministic-demo",
        "database": database_status(),
        "environment": SETTINGS.environment,
        "demo_mode": SETTINGS.demo_mode,
        "organizations": db.scalar(select(func.count()).select_from(Organization)),
        "time": now().isoformat(),
    }


# Authentication and workspaces
@app.post("/api/v1/auth/login")
@app.post("/api/auth/login")
def login(body: LoginRequest, request: Request, db: Session = Depends(get_session)) -> dict[str, Any]:
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not user.active or not verify_secret(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Use documented demo credentials.")
    access = issue_token()
    refresh = issue_token("fsr")
    session = TokenSession(
        id=make_id("session"),
        user_id=user.id,
        token_hash=token_hash(access),
        refresh_hash=token_hash(refresh),
        expires_at=expires_in(),
        revoked_at=None,
        created_at=now(),
        updated_at=now(),
    )
    db.add(session)
    db.commit()
    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    default_org = memberships[0].organization_id if memberships else DEMO_ORG
    role = next((m.role for m in memberships if m.organization_id == default_org), "Platform Admin")
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "workspace_id": default_org,
        "user": {"id": user.id, "name": user.name, "email": user.email, "role": role},
    }


@app.post("/api/v1/auth/refresh")
@app.post("/api/auth/refresh")
def refresh(
    refresh_token: str = Header(alias="X-Refresh-Token"), db: Session = Depends(get_session)
) -> dict[str, Any]:
    session = db.scalar(
        select(TokenSession).where(
            TokenSession.refresh_hash == token_hash(refresh_token), TokenSession.revoked_at.is_(None)
        )
    )
    if not session:
        raise HTTPException(status_code=401, detail="Refresh token is invalid.")
    access = issue_token()
    session.token_hash = token_hash(access)
    session.expires_at = expires_in()
    session.updated_at = now()
    db.commit()
    return {"access_token": access, "token_type": "bearer"}


@app.post("/api/v1/auth/logout")
@app.post("/api/auth/logout")
def logout(
    authorization: Annotated[str | None, Header()] = None, db: Session = Depends(get_session)
) -> dict[str, Any]:
    if authorization and authorization.lower().startswith("bearer "):
        session = db.scalar(
            select(TokenSession).where(
                TokenSession.token_hash == token_hash(authorization.split(" ", 1)[1])
            )
        )
        if session:
            session.revoked_at = now()
            session.updated_at = now()
            db.commit()
    return {"ok": True}


@app.get("/api/v1/auth/me")
@app.get("/api/auth/me")
def me(ctx: Context = Depends(get_context), db: Session = Depends(get_session)) -> dict[str, Any]:
    workspaces = [
        compact_org(db.get(Organization, m.organization_id)) | {"role": m.role}
        for m in db.scalars(select(Membership).where(Membership.user_id == ctx.user_id)).all()
    ]
    return {
        "id": ctx.user_id,
        "name": ctx.user_name,
        "role": ctx.role,
        "organization": compact_org(db.get(Organization, ctx.organization_id)),
        "workspaces": workspaces,
    }


@app.get("/api/v1/workspaces")
def workspaces(
    ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> list[dict[str, Any]]:
    memberships = db.scalars(select(Membership).where(Membership.user_id == ctx.user_id)).all()
    return [
        compact_org(db.get(Organization, item.organization_id))
        | {"role": item.role, "active": item.organization_id == ctx.organization_id}
        for item in memberships
    ]


# Dashboard, geospatial command map, projects and missions
@app.get("/api/v1/dashboard")
@app.get("/api/dashboard")
def dashboard(ctx: Context = Depends(get_context), db: Session = Depends(get_session)) -> dict[str, Any]:
    projects = db.scalars(select(Project).where(Project.organization_id == ctx.organization_id)).all()
    findings = db.scalars(select(Finding).where(Finding.organization_id == ctx.organization_id)).all()
    devices = db.scalars(select(Device).where(Device.organization_id == ctx.organization_id)).all()
    work_orders = db.scalars(
        select(WorkOrder).where(WorkOrder.organization_id == ctx.organization_id)
    ).all()
    recent = db.scalars(
        select(MediaFile)
        .where(MediaFile.organization_id == ctx.organization_id)
        .order_by(desc(MediaFile.captured_at))
        .limit(6)
    ).all()
    return {
        "kpis": {
            "active_projects": len(projects),
            "new_findings": sum(
                1 for x in findings if aware_datetime(x.created_at) > now() - timedelta(days=1)
            ),
            "critical_defects": sum(
                1 for x in findings if x.severity == "critical" and x.review_state != "rejected"
            ),
            "pending_review": sum(1 for x in findings if x.review_state in {"pending", "uncertain"}),
            "open_work_orders": sum(1 for x in work_orders if x.status not in {"Verified", "Cancelled"}),
            "sync_queue": sum((d.health or {}).get("queue_count", 0) for d in devices),
        },
        "priority": [
            finding_out(x, db)
            for x in sorted(
                [x for x in findings if x.severity in {"critical", "high"}],
                key=lambda f: (f.severity != "critical", -f.confidence),
            )[:8]
        ],
        "recent_uploads": [media_out(x) for x in recent],
        "projects": [project_out(x, db) for x in projects],
        "devices": [device_out(x, db) for x in devices],
        "work_orders": [work_order_out(x) for x in work_orders[:5]],
        "insight": "Evidence-first priorities combine verified defects, queued edge captures, inspection coverage, and synthetic demo risk scores.",
        "quality_notice": "All local data, coordinates, imagery, and model metrics are synthetic demo records.",
    }


@app.get("/api/v1/projects")
@app.get("/api/projects")
def list_projects(
    ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> list[dict[str, Any]]:
    return [
        project_out(x, db)
        for x in db.scalars(select(Project).where(Project.organization_id == ctx.organization_id)).all()
    ]


@app.post("/api/v1/projects")
@app.post("/api/projects")
def create_project(
    payload: dict[str, Any],
    request: Request,
    ctx: Context = Depends(require("mission:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    project = Project(
        id=make_id("prj"),
        organization_id=ctx.organization_id,
        name=str(payload.get("name", "Untitled project")),
        industry=str(payload.get("industry", "Infrastructure")),
        status="Planning",
        metadata_json={"created_from": "api"},
        created_at=now(),
        updated_at=now(),
    )
    db.add(project)
    audit(db, ctx, request, "Created project", "project", project.id)
    db.commit()
    return project_out(project, db)


@app.get("/api/v1/projects/{project_id}")
@app.get("/api/projects/{project_id}")
def project_detail(
    project_id: str, ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> dict[str, Any]:
    project = org_item(db, Project, project_id, ctx)
    sites = db.scalars(select(Site).where(Site.project_id == project.id)).all()
    return project_out(project, db) | {
        "sites": [
            {"id": s.id, "name": s.name, "coverage": s.coverage_percent, "risk": s.risk_score}
            for s in sites
        ],
        "assets": db.scalar(
            select(func.count()).select_from(Asset).join(Site).where(Site.project_id == project.id)
        ),
    }


@app.patch("/api/v1/projects/{project_id}")
@app.patch("/api/projects/{project_id}")
def update_project(
    project_id: str,
    payload: dict[str, Any],
    request: Request,
    ctx: Context = Depends(require("mission:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    project = org_item(db, Project, project_id, ctx)
    for key in {"name", "industry", "status"}:
        if key in payload:
            setattr(project, key, str(payload[key]))
    project.updated_at = now()
    audit(db, ctx, request, "Updated project", "project", project.id)
    db.commit()
    return project_out(project, db)


@app.get("/api/v1/map/command")
def command_map(
    project_id: str | None = None,
    severity: str | None = None,
    review_state: str | None = None,
    bbox: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    ctx: Context = Depends(get_context),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    projects_query = select(Project).where(Project.organization_id == ctx.organization_id)
    if project_id:
        projects_query = projects_query.where(Project.id == project_id)
    projects = db.scalars(projects_query).all()
    project_ids = [p.id for p in projects]
    sites = (
        db.scalars(
            select(Site).where(
                Site.organization_id == ctx.organization_id, Site.project_id.in_(project_ids)
            )
        ).all()
        if project_ids
        else []
    )
    site_ids = [s.id for s in sites]
    assets = (
        db.scalars(
            select(Asset).where(Asset.organization_id == ctx.organization_id, Asset.site_id.in_(site_ids))
        ).all()
        if site_ids
        else []
    )
    if bbox:
        try:
            min_lng, min_lat, max_lng, max_lat = [float(x) for x in bbox.split(",")]
            assets = [
                a for a in assets if min_lat <= a.latitude <= max_lat and min_lng <= a.longitude <= max_lng
            ]
        except ValueError:
            raise HTTPException(status_code=422, detail="bbox must be minLng,minLat,maxLng,maxLat")
    asset_ids = [a.id for a in assets]
    q = (
        select(Finding).where(
            Finding.organization_id == ctx.organization_id, Finding.asset_id.in_(asset_ids)
        )
        if asset_ids
        else select(Finding).where(False)
    )
    if severity:
        q = q.where(Finding.severity == severity)
    if review_state:
        q = q.where(Finding.review_state == review_state)
    findings = db.scalars(q).all()
    devices = db.scalars(select(Device).where(Device.organization_id == ctx.organization_id)).all()
    work_orders = db.scalars(
        select(WorkOrder).where(WorkOrder.organization_id == ctx.organization_id)
    ).all()
    return {
        "projects": [project_out(p, db) for p in projects],
        "sites": [
            {
                "id": s.id,
                "project_id": s.project_id,
                "name": s.name,
                "lat": s.latitude,
                "lng": s.longitude,
                "risk": s.risk_score,
                "coverage": s.coverage_percent,
                "boundary": s.boundary,
            }
            for s in sites
        ],
        "assets": [asset_out(a, db) for a in assets],
        "detections": [finding_out(f, db) for f in findings],
        "devices": [device_out(d, db) for d in devices],
        "work_orders": [work_order_out(w) for w in work_orders],
        "flight_paths": [
            {
                "mission_id": "mission-alpha-1",
                "coordinates": [[73.058, 33.615], [73.064, 33.618], [73.067, 33.621], [73.073, 33.623]],
            }
        ],
        "layers": {
            "risk_heatmap": "synthetic rule-assisted density",
            "coverage": "seeded inspection coverage",
            "postgis": False,
            "fallback": "latitude/longitude plus bounding-box query",
        },
    }


@app.get("/api/sites/map")
def legacy_site_map(
    project_id: str = "prj-solar-alpha",
    severity: str | None = None,
    review_state: str | None = None,
    ctx: Context = Depends(get_context),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    result = command_map(project_id, severity, review_state, None, None, None, ctx, db)
    result["flight_path"] = [[33.615, 73.058], [33.618, 73.064], [33.621, 73.067], [33.623, 73.073]]
    return result


@app.get("/api/v1/missions")
def missions(
    ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Mission)
        .where(Mission.organization_id == ctx.organization_id)
        .order_by(desc(Mission.created_at))
    ).all()
    return [mission_out(x, db) for x in rows]


def mission_out(m: Mission, db: Session) -> dict[str, Any]:
    capture_count = (
        db.scalar(select(func.count()).select_from(MediaFile).where(MediaFile.mission_id == m.id)) or 0
    )
    return {
        "id": m.id,
        "name": m.name,
        "project_id": m.project_id,
        "site_id": m.site_id,
        "mission_type": m.mission_type,
        "state": m.state,
        "priority": m.priority,
        "assigned_operator": m.assigned_operator,
        "assigned_device_id": m.assigned_device_id,
        "due_date": m.due_date,
        "zones": m.zones,
        "checklist": m.checklist,
        "capture_count": capture_count,
        "settings": m.settings,
        "created_at": m.created_at.isoformat(),
    }


@app.post("/api/v1/missions")
def create_mission(
    body: MissionRequest,
    request: Request,
    ctx: Context = Depends(require("mission:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    project = org_item(db, Project, body.project_id, ctx)
    site = org_item(db, Site, body.site_id, ctx)
    if site.project_id != project.id:
        raise HTTPException(status_code=422, detail="Site does not belong to selected project.")
    device_id = body.assigned_device_id
    if device_id:
        org_item(db, Device, device_id, ctx)
    mission = Mission(
        id=make_id("mission"),
        organization_id=ctx.organization_id,
        project_id=project.id,
        site_id=site.id,
        name=body.name,
        mission_type=body.mission_type,
        state="Planned",
        priority=body.priority,
        assigned_operator=body.assigned_operator,
        assigned_device_id=device_id,
        due_date=body.due_date,
        zones=body.zones,
        checklist=[
            {"label": "Safety brief", "done": False},
            {"label": "Minimum resolution check", "done": False},
        ],
        settings={"offline_enabled": body.offline_enabled, "review_policy": "critical-human-confirmation"},
        created_at=now(),
        updated_at=now(),
    )
    db.add(mission)
    audit(db, ctx, request, "Created mission", "mission", mission.id, project_id=project.id)
    db.commit()
    return mission_out(mission, db)


@app.get("/api/v1/missions/{mission_id}")
def mission_detail(
    mission_id: str, ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> dict[str, Any]:
    mission = org_item(db, Mission, mission_id, ctx)
    media = db.scalars(select(MediaFile).where(MediaFile.mission_id == mission.id)).all()
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.organization_id == ctx.organization_id, AuditEvent.target_id == mission.id)
        .order_by(desc(AuditEvent.occurred_at))
    ).all()
    return mission_out(mission, db) | {
        "media": [media_out(x) for x in media],
        "audit": [audit_out(x) for x in events],
        "device": device_out(db.get(Device, mission.assigned_device_id), db)
        if mission.assigned_device_id and db.get(Device, mission.assigned_device_id)
        else None,
    }


# Media intake and evidence lineage
@app.get("/api/v1/media")
@app.get("/api/inspections/media")
def media_list(
    asset_id: str | None = None,
    limit: int = 20,
    ctx: Context = Depends(get_context),
    db: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    q = select(MediaFile).where(MediaFile.organization_id == ctx.organization_id)
    if asset_id:
        q = q.where(MediaFile.asset_id == asset_id)
    return [
        media_out(x)
        for x in db.scalars(q.order_by(desc(MediaFile.captured_at)).limit(min(limit, 200))).all()
    ]


@app.post("/api/v1/media/intake")
@app.post("/api/inspections/upload")
async def intake_media(
    request: Request,
    file: UploadFile = File(...),
    asset_id: str | None = Form(default=None),
    site_id: str | None = Form(default=None),
    mission_id: str | None = Form(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: Context = Depends(require("media:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    content = await file.read()
    validation = assess_media(content, file.filename or "upload.jpg", file.content_type)
    if validation["errors"]:
        raise HTTPException(status_code=422, detail={"validation": validation})
    asset = org_item(db, Asset, asset_id, ctx) if asset_id else None
    if not site_id and asset:
        site_id = asset.site_id
    if not site_id:
        site = db.scalar(select(Site).where(Site.organization_id == ctx.organization_id).limit(1))
        site_id = site.id if site else None
    if not site_id:
        raise HTTPException(status_code=422, detail="A site or asset is required for intake.")
    site = org_item(db, Site, site_id, ctx)
    if mission_id:
        org_item(db, Mission, mission_id, ctx)
    digest = checksum(content)
    existing = db.scalar(
        select(MediaFile).where(
            MediaFile.organization_id == ctx.organization_id, MediaFile.checksum == digest
        )
    )
    if existing:
        validation["duplicate_check"] = "duplicate"
        return {
            "duplicate": True,
            "media": media_out(existing),
            "validation": validation,
            "inference_job": None,
        }
    if idempotency_key:
        prior = db.scalar(
            select(MediaFile).where(
                MediaFile.organization_id == ctx.organization_id,
                MediaFile.storage_key == f"idempotency/{idempotency_key}",
            )
        )
        if prior:
            return {
                "duplicate": True,
                "media": media_out(prior),
                "validation": prior.validation,
                "inference_job": None,
            }
    storage_key = (
        f"idempotency/{idempotency_key}"
        if idempotency_key
        else f"{ctx.organization_id}/{now().strftime('%Y%m%d')}/{make_id('media')}-{file.filename or 'upload.jpg'}"
    )
    storage.put(storage_key, content)
    validation["duplicate_check"] = "unique"
    media = MediaFile(
        id=make_id("media"),
        organization_id=ctx.organization_id,
        asset_id=asset.id if asset else None,
        site_id=site.id,
        mission_id=mission_id,
        device_id=None,
        filename=file.filename or "upload.jpg",
        content_type=file.content_type or "application/octet-stream",
        storage_key=storage_key,
        checksum=digest,
        byte_size=len(content),
        captured_at=now(),
        latitude=asset.latitude if asset else site.latitude,
        longitude=asset.longitude if asset else site.longitude,
        width=1920,
        height=1080,
        source="Manual upload",
        validation=validation,
        quality={
            "score": round(
                (validation["blur_score"] + validation["brightness_score"] + validation["resolution_score"])
                / 3
                * 100
            ),
            "warnings": validation["warnings"],
        },
        created_at=now(),
        updated_at=now(),
    )
    db.add(media)
    audit(
        db,
        ctx,
        request,
        "Validated and stored media",
        "media",
        media.id,
        validation_state=validation["state"],
    )
    db.flush()
    finding = run_deterministic_inference(db, ctx, media, request, idempotency_key=f"infer:{media.id}")
    db.commit()
    return {
        "duplicate": False,
        "media": media_out(media),
        "validation": validation,
        "inference_job": finding.inference_job_id,
        "finding": finding_out(finding, db),
    }


@app.get("/api/v1/media/{media_id}/lineage")
def media_lineage(
    media_id: str, ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> dict[str, Any]:
    media = org_item(db, MediaFile, media_id, ctx)
    findings = db.scalars(select(Finding).where(Finding.media_id == media.id)).all()
    chain: list[dict[str, Any]] = [
        {
            "step": "Original Media",
            "entity": "media",
            "id": media.id,
            "at": media.captured_at.isoformat(),
            "detail": media.filename,
        }
    ]
    for f in findings:
        job = db.get(InferenceJob, f.inference_job_id) if f.inference_job_id else None
        chain += [
            {
                "step": "Inference Job",
                "entity": "inference_job",
                "id": job.id if job else "seeded",
                "at": job.created_at.isoformat() if job else f.created_at.isoformat(),
                "detail": job.provider if job else "seeded deterministic result",
            },
            {
                "step": "Finding",
                "entity": "finding",
                "id": f.id,
                "at": f.created_at.isoformat(),
                "detail": f.defect_class,
            },
            {
                "step": "Reviewer Decision",
                "entity": "review",
                "id": f.id,
                "at": f.updated_at.isoformat(),
                "detail": f.reviewer_decision or "awaiting review",
            },
        ]
        defect = db.scalar(select(Defect).where(Defect.finding_id == f.id))
        work = db.scalar(select(WorkOrder).where(WorkOrder.finding_id == f.id))
        if defect:
            chain.append(
                {
                    "step": "Verified Defect",
                    "entity": "defect",
                    "id": defect.id,
                    "at": defect.created_at.isoformat(),
                    "detail": defect.state,
                }
            )
        if work:
            chain.append(
                {
                    "step": "Work Order",
                    "entity": "work_order",
                    "id": work.id,
                    "at": work.created_at.isoformat(),
                    "detail": work.status,
                }
            )
    return {
        "media": media_out(media),
        "lineage": chain,
        "notice": "Evidence is append-only in this demo; reviewer decisions never overwrite original AI output.",
    }


@app.get("/api/inspections/media/{media_id}/annotations")
def annotations(
    media_id: str, ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> dict[str, Any]:
    lineage = media_lineage(media_id, ctx, db)
    findings = db.scalars(select(Finding).where(Finding.media_id == media_id)).all()
    return {
        "media": lineage["media"],
        "detections": [finding_out(x, db) for x in findings],
        "evidence_chain": lineage["lineage"],
    }


@app.post("/api/v1/inference/media/{media_id}/run")
@app.post("/api/inspections/{media_id}/trigger-inference")
def trigger_inference(
    media_id: str,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ctx: Context = Depends(require("media:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    media = org_item(db, MediaFile, media_id, ctx)
    finding = run_deterministic_inference(db, ctx, media, request, idempotency_key)
    db.commit()
    return finding_out(finding, db)


@app.get("/api/v1/inference/jobs")
@app.get("/api/inspections/inference-runs")
def inference_jobs(
    ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> list[dict[str, Any]]:
    jobs = db.scalars(
        select(InferenceJob)
        .where(InferenceJob.organization_id == ctx.organization_id)
        .order_by(desc(InferenceJob.created_at))
        .limit(100)
    ).all()
    return [
        {
            "id": j.id,
            "media_id": j.media_id,
            "model": j.model_version_id,
            "provider": j.provider,
            "status": j.state,
            "duration_ms": j.duration_ms,
            "created_at": j.created_at.isoformat(),
            "error": j.error,
        }
        for j in jobs
    ]


# Findings/review/defects/work orders
@app.get("/api/v1/findings")
@app.get("/api/defects")
def findings_list(
    severity: str | None = None,
    review_state: str | None = None,
    status: str | None = None,
    ctx: Context = Depends(get_context),
    db: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    q = select(Finding).where(Finding.organization_id == ctx.organization_id)
    if severity:
        q = q.where(Finding.severity == severity)
    if review_state:
        q = q.where(Finding.review_state == review_state)
    rows = db.scalars(q.order_by(desc(Finding.created_at))).all()
    output = [finding_out(x, db) for x in rows]
    if status:
        output = [x for x in output if x.get("work_order") and x["work_order"]["status"] == status]
    return output


@app.post("/api/v1/findings/{finding_id}/review")
@app.post("/api/defects/{finding_id}/review")
def review_finding(
    finding_id: str,
    body: ReviewRequest,
    request: Request,
    ctx: Context = Depends(require("review:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    f = org_item(db, Finding, finding_id, ctx)
    # The original detector output remains immutable; human corrections are stored separately.
    f.reviewed_by = ctx.user_id
    f.reviewer_decision = body.decision
    f.reviewer_note = body.note
    f.training_candidate = body.training_candidate
    f.updated_at = now()
    if body.decision == "approve":
        f.review_state = "verified"
        f.human_override = {
            "severity": body.severity or f.severity,
            "defect_class": body.defect_type or f.defect_class,
            "at": now().isoformat(),
            "by": ctx.user_id,
        }
        if body.severity:
            f.severity = body.severity
        if body.defect_type and body.defect_type in TAXONOMY:
            f.defect_class = body.defect_type
        defect = db.scalar(select(Defect).where(Defect.finding_id == f.id))
        if not defect and f.asset_id:
            defect = Defect(
                id=make_id("defect"),
                organization_id=ctx.organization_id,
                asset_id=f.asset_id,
                finding_id=f.id,
                title=f"Verified {TAXONOMY.get(f.defect_class, {}).get('label', f.defect_class)}",
                state="Verified",
                severity=f.severity,
                created_at=now(),
                updated_at=now(),
            )
            db.add(defect)
    elif body.decision == "reject":
        f.review_state = "rejected"
    elif body.decision == "uncertain":
        f.review_state = "uncertain"
    else:
        f.review_state = "escalated"
    if f.asset_id:
        asset = db.get(Asset, f.asset_id)
        if asset:
            recompute_risk(db, asset, ctx)
    audit(
        db,
        ctx,
        request,
        f"Reviewer {body.decision} decision",
        "finding",
        f.id,
        note=body.note,
        training_candidate=body.training_candidate,
    )
    db.commit()
    return finding_out(f, db)


@app.post("/api/v1/findings/{finding_id}/work-orders")
@app.post("/api/defects/{finding_id}/work-orders")
def create_work_order(
    finding_id: str,
    body: WorkOrderRequest,
    request: Request,
    ctx: Context = Depends(require("workorder:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    f = org_item(db, Finding, finding_id, ctx)
    if f.review_state != "verified":
        raise HTTPException(
            status_code=422, detail="A human verified finding is required before work-order creation."
        )
    existing = db.scalar(select(WorkOrder).where(WorkOrder.finding_id == f.id))
    if existing:
        return work_order_out(existing)
    if not f.asset_id:
        raise HTTPException(status_code=422, detail="Finding lacks asset relationship.")
    defect = db.scalar(select(Defect).where(Defect.finding_id == f.id))
    title = (
        body.title
        or f"Remediate {TAXONOMY.get(f.defect_class, {}).get('label', f.defect_class)} — {f.asset_id.upper()}"
    )
    status = (
        "Awaiting approval" if f.severity == "critical" or (body.estimated_cost or 0) > 5000 else "Approved"
    )
    work = WorkOrder(
        id=make_id("wo"),
        organization_id=ctx.organization_id,
        asset_id=f.asset_id,
        finding_id=f.id,
        defect_id=defect.id if defect else None,
        mission_id=None,
        title=title,
        description="AI-assisted recommendation requires human maintenance approval.",
        severity=f.severity,
        priority=f.severity,
        status=status,
        assignee=body.assignee,
        due_date=body.due_date or (now() + timedelta(days=3)).date().isoformat(),
        estimated_cost=body.estimated_cost,
        checklist=[
            {"task": "Confirm safety controls", "done": False},
            {"task": "Attach resolution evidence", "done": False},
            {"task": "Request verification inspection", "done": False},
        ],
        resolution_evidence=[],
        approval_history=[],
        created_at=now(),
        updated_at=now(),
    )
    db.add(work)
    if status == "Awaiting approval":
        create_alert(
            db,
            ctx,
            "work_order_approval",
            "high",
            f"Work order requires approval: {title}",
            "work_order",
            work.id,
        )
    audit(
        db,
        ctx,
        request,
        "Created human-approved work order draft",
        "work_order",
        work.id,
        finding_id=f.id,
        status=status,
    )
    db.commit()
    return work_order_out(work)


@app.get("/api/v1/work-orders")
def work_orders(
    status: str | None = None, ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> list[dict[str, Any]]:
    q = select(WorkOrder).where(WorkOrder.organization_id == ctx.organization_id)
    if status:
        q = q.where(WorkOrder.status == status)
    return [work_order_out(x) for x in db.scalars(q.order_by(desc(WorkOrder.created_at))).all()]


@app.post("/api/v1/work-orders/{work_order_id}/approve")
def approve_work_order(
    work_order_id: str,
    request: Request,
    ctx: Context = Depends(require_approval),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    work = org_item(db, WorkOrder, work_order_id, ctx)
    if work.status not in {"Awaiting approval", "Draft"}:
        raise HTTPException(status_code=422, detail="Work order is not awaiting approval.")
    work.status = "Approved"
    work.approval_history = [
        *work.approval_history,
        {"at": now().isoformat(), "by": ctx.user_name, "decision": "approved"},
    ]
    work.updated_at = now()
    audit(db, ctx, request, "Approved work order", "work_order", work.id)
    db.commit()
    return work_order_out(work)


@app.post("/api/v1/work-orders/{work_order_id}/complete")
def complete_work_order(
    work_order_id: str,
    request: Request,
    note: str = "Synthetic resolution evidence attached",
    ctx: Context = Depends(require("workorder:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    work = org_item(db, WorkOrder, work_order_id, ctx)
    if work.status not in {
        "Approved",
        "Assigned",
        "In progress",
        "Waiting for parts",
        "Waiting for access",
    }:
        raise HTTPException(status_code=422, detail="Work order cannot be completed from current state.")
    work.status = "Verification required"
    work.resolution_evidence = [
        *work.resolution_evidence,
        {"at": now().isoformat(), "by": ctx.user_name, "note": note, "synthetic": True},
    ]
    work.updated_at = now()
    audit(db, ctx, request, "Completed work order and attached resolution evidence", "work_order", work.id)
    db.commit()
    return work_order_out(work)


@app.post("/api/v1/work-orders/{work_order_id}/verify")
def verify_work_order(
    work_order_id: str,
    request: Request,
    ctx: Context = Depends(require("review:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    work = org_item(db, WorkOrder, work_order_id, ctx)
    if not work.resolution_evidence:
        raise HTTPException(status_code=422, detail="Resolution evidence is required before verification.")
    work.status = "Verified"
    work.approval_history = [
        *work.approval_history,
        {"at": now().isoformat(), "by": ctx.user_name, "decision": "verification approved"},
    ]
    work.updated_at = now()
    audit(db, ctx, request, "Verified work-order closure", "work_order", work.id)
    db.commit()
    return work_order_out(work)


# Assets / risk / changes
@app.get("/api/v1/assets/{asset_id}")
@app.get("/api/assets/{asset_id}")
def asset_detail(
    asset_id: str, ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> dict[str, Any]:
    asset = org_item(db, Asset, asset_id, ctx)
    media = db.scalars(
        select(MediaFile).where(MediaFile.asset_id == asset.id).order_by(desc(MediaFile.captured_at))
    ).all()
    findings = db.scalars(
        select(Finding).where(Finding.asset_id == asset.id).order_by(desc(Finding.created_at))
    ).all()
    works = db.scalars(
        select(WorkOrder).where(WorkOrder.asset_id == asset.id).order_by(desc(WorkOrder.created_at))
    ).all()
    snapshot = recompute_risk(db, asset, ctx)
    db.commit()
    timeline = [
        {"date": x.captured_at.date().isoformat(), "event": "Inspection capture", "source": x.source}
        for x in media[:8]
    ]
    timeline += [
        {
            "date": x.updated_at.date().isoformat(),
            "event": f"Finding {x.review_state}",
            "source": x.reviewer_note or "AI inference",
        }
        for x in findings[:5]
    ]
    return {
        "asset": asset_out(asset, db)
        | {"risk_score": snapshot.score, "risk_level": snapshot.level, "risk_drivers": snapshot.drivers},
        "media": [media_out(x) for x in media[:12]],
        "detections": [finding_out(x, db) for x in findings],
        "work_orders": [work_order_out(x) for x in works],
        "timeline": sorted(timeline, key=lambda x: x["date"], reverse=True),
        "evidence_lineage": f"/api/v1/assets/{asset.id}/lineage",
    }


@app.get("/api/v1/assets/{asset_id}/risk")
def asset_risk(
    asset_id: str, ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> dict[str, Any]:
    asset = org_item(db, Asset, asset_id, ctx)
    snapshot = recompute_risk(db, asset, ctx)
    db.commit()
    return {
        "asset": asset_out(asset, db),
        "score": snapshot.score,
        "level": snapshot.level,
        "drivers": snapshot.drivers,
        "notice": "Explainable asset-risk score: a synthetic baseline rule model, not a predictive-maintenance accuracy claim.",
    }


@app.get("/api/v1/risk/center")
def risk_center(ctx: Context = Depends(get_context), db: Session = Depends(get_session)) -> dict[str, Any]:
    assets = db.scalars(select(Asset).where(Asset.organization_id == ctx.organization_id)).all()
    cards = []
    for asset in assets[:100]:
        snap = db.scalar(
            select(AssetRiskSnapshot)
            .where(AssetRiskSnapshot.asset_id == asset.id)
            .order_by(desc(AssetRiskSnapshot.created_at))
        )
        if snap:
            cards.append(
                {
                    "asset": asset_out(asset, db),
                    "score": snap.score,
                    "level": snap.level,
                    "drivers": snap.drivers,
                }
            )
    return {
        "high_risk_assets": sorted(cards, key=lambda x: x["score"], reverse=True)[:15],
        "by_level": {
            level: sum(1 for x in cards if x["level"] == level)
            for level in ["Critical", "High", "Moderate", "Low"]
        },
        "method": "Transparent baseline risk scoring from findings, work-order state, freshness, and quality warnings.",
    }


@app.get("/api/v1/assets/{asset_id}/changes")
def asset_changes(
    asset_id: str,
    baseline_date: str | None = None,
    comparison_date: str | None = None,
    ctx: Context = Depends(get_context),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    asset = org_item(db, Asset, asset_id, ctx)
    media = db.scalars(
        select(MediaFile).where(MediaFile.asset_id == asset.id).order_by(MediaFile.captured_at)
    ).all()
    if len(media) < 2:
        raise HTTPException(status_code=422, detail="At least two captures are needed for comparison.")
    baseline, current = media[0], media[-1]
    findings = db.scalars(select(Finding).where(Finding.asset_id == asset.id)).all()
    severity_delta = "increased" if any(x.severity in {"high", "critical"} for x in findings) else "stable"
    return {
        "asset": asset_out(asset, db),
        "baseline": media_out(baseline),
        "comparison": media_out(current),
        "baseline_date": baseline_date or baseline.captured_at.date().isoformat(),
        "comparison_date": comparison_date or current.captured_at.date().isoformat(),
        "results": [
            {
                "type": "new defect" if findings else "no material change",
                "severity_delta": severity_delta,
                "detail": "Deterministic local comparison based on seeded capture and finding metadata.",
            }
        ],
        "finding_delta": {
            "new": len(findings),
            "resolved": 0,
            "worsened": 1 if severity_delta == "increased" else 0,
        },
        "notice": "This is deterministic comparison logic for demo data; it is not pixel-level change detection.",
    }


# Device fleet and persisted offline sync
@app.get("/api/v1/devices")
@app.get("/api/devices")
def devices(
    ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> dict[str, Any] | list[dict[str, Any]]:
    rows = db.scalars(select(Device).where(Device.organization_id == ctx.organization_id)).all()
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.organization_id == ctx.organization_id)
        .order_by(desc(AuditEvent.occurred_at))
        .limit(10)
    ).all()
    # Preserve phase 1 response shape for /api/devices.
    return {"devices": [device_out(x, db) for x in rows], "events": [audit_out(x) for x in events]}


@app.get("/api/v1/devices/{device_id}")
def device_detail(
    device_id: str, ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> dict[str, Any]:
    device = org_item(db, Device, device_id, ctx)
    jobs = db.scalars(
        select(SyncJob).where(SyncJob.device_id == device.id).order_by(desc(SyncJob.created_at))
    ).all()
    return device_out(device, db) | {
        "sync_jobs": [sync_out(x) for x in jobs],
        "configuration": device.config,
        "health_events": [
            audit_out(x)
            for x in db.scalars(
                select(AuditEvent)
                .where(AuditEvent.target_id == device.id)
                .order_by(desc(AuditEvent.occurred_at))
                .limit(10)
            ).all()
        ],
    }


def sync_out(j: SyncJob) -> dict[str, Any]:
    return {
        "id": j.id,
        "device_id": j.device_id,
        "media_id": j.media_id,
        "state": j.state,
        "retry_count": j.retry_count,
        "error": j.error,
        "created_at": j.created_at.isoformat(),
    }


@app.post("/api/v1/devices/{device_id}/mode")
@app.post("/api/devices/{device_id}/mode")
def set_device_mode(
    device_id: str,
    body: DeviceModeRequest,
    request: Request,
    ctx: Context = Depends(require("device:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    device = org_item(db, Device, device_id, ctx)
    device.state = body.mode
    device.last_seen_at = now()
    device.updated_at = now()
    audit(db, ctx, request, f"Set device mode to {body.mode}", "device", device.id)
    db.commit()
    return device_out(device, db)


@app.post("/api/v1/devices/{device_id}/capture")
def device_capture(
    device_id: str,
    request: Request,
    failure: str | None = None,
    ctx: Context = Depends(require("device:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    device = org_item(db, Device, device_id, ctx)
    if not device.site_id:
        raise HTTPException(status_code=422, detail="Device has no assigned site.")
    asset = db.scalar(
        select(Asset)
        .where(Asset.site_id == device.site_id, Asset.organization_id == ctx.organization_id)
        .limit(1)
    )
    content = b"FIELDSIGHT-SYNTHETIC-EDGE-CAPTURE" + device.id.encode()
    media = MediaFile(
        id=make_id("media"),
        organization_id=ctx.organization_id,
        asset_id=asset.id if asset else None,
        site_id=device.site_id,
        mission_id=None,
        device_id=device.id,
        filename=f"{device.name.lower()}_{now().strftime('%H%M%S')}.jpg",
        content_type="image/jpeg",
        storage_key=f"edge/{device.id}/{make_id('capture')}.jpg",
        checksum=checksum(content + now().isoformat().encode()),
        byte_size=len(content),
        captured_at=now(),
        latitude=asset.latitude if asset else None,
        longitude=asset.longitude if asset else None,
        width=1920,
        height=1080,
        source=f"Edge · {device.name}",
        validation={
            "state": "Warning" if failure else "Healthy",
            "synthetic": True,
            "device_time_drift": failure == "time-drift",
        },
        quality={"score": 76 if failure else 91, "warnings": [failure] if failure else []},
        created_at=now(),
        updated_at=now(),
    )
    db.add(media)
    db.flush()
    state = "Queued offline" if device.state in {"offline", "degraded"} else "Ready to synchronize"
    sync = SyncJob(
        id=make_id("sync"),
        organization_id=ctx.organization_id,
        device_id=device.id,
        media_id=media.id,
        state="Failed" if failure == "corrupt-file" else state,
        retry_count=0,
        idempotency_key=f"capture:{device.id}:{media.id}",
        error="Synthetic corrupt file simulation" if failure == "corrupt-file" else None,
        created_at=now(),
        updated_at=now(),
    )
    db.add(sync)
    health = dict(device.health)
    health["queue_count"] = int(health.get("queue_count", 0)) + 1
    device.health = health
    device.updated_at = now()
    audit(
        db,
        ctx,
        request,
        "Captured media into persisted edge queue",
        "device",
        device.id,
        sync_state=sync.state,
    )
    db.commit()
    return {"media": media_out(media), "sync_job": sync_out(sync), "device": device_out(device, db)}


@app.post("/api/v1/devices/{device_id}/sync")
@app.post("/api/devices/{device_id}/sync")
def sync_device(
    device_id: str,
    request: Request,
    ctx: Context = Depends(require("device:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    device = org_item(db, Device, device_id, ctx)
    device.state = "syncing"
    device.last_seen_at = now()
    jobs = db.scalars(
        select(SyncJob).where(
            SyncJob.device_id == device.id,
            SyncJob.state.in_(["Queued offline", "Ready to synchronize", "Retry scheduled"]),
        )
    ).all()
    created: list[dict[str, Any]] = []
    for job in jobs:
        if job.media_id:
            media = db.get(MediaFile, job.media_id)
            if media:
                finding = run_deterministic_inference(
                    db, ctx, media, request, idempotency_key=f"sync:{job.id}"
                )
                created.append(finding_out(finding, db))
        job.state = "Synchronized"
        job.retry_count += 1
        job.updated_at = now()
    health = dict(device.health)
    health["queue_count"] = 0
    device.health = health
    device.state = "online"
    device.updated_at = now()
    audit(db, ctx, request, "Completed retry-safe edge sync", "device", device.id, jobs=len(jobs))
    db.commit()
    return {"device": device_out(device, db), "synchronized_jobs": len(jobs), "findings": created}


# Models, datasets, alerts, quality and governance
@app.get("/api/v1/models")
@app.get("/api/models")
def models(ctx: Context = Depends(get_context), db: Session = Depends(get_session)) -> dict[str, Any]:
    rows = db.scalars(select(ModelVersion).order_by(ModelVersion.version)).all()
    out = []
    for m in rows:
        metrics = m.metrics or {}
        out.append(
            {
                "id": m.id,
                "version": m.version,
                "status": "production" if m.state == "Deployed" else m.state.lower(),
                "state": m.state,
                "precision": metrics.get("precision_proxy", 0),
                "recall": metrics.get("recall_proxy", 0),
                "drift": metrics.get("drift", 0),
                "model_card": m.model_card,
                "deployed_to": db.scalar(
                    select(func.count()).select_from(Device).where(Device.model_version == m.version)
                )
                or 0,
            }
        )
    return {
        "models": out,
        "confidence_distribution": [
            {"range": "0.50–0.60", "count": 9},
            {"range": "0.60–0.70", "count": 24},
            {"range": "0.70–0.80", "count": 51},
            {"range": "0.80–0.90", "count": 46},
            {"range": "0.90–1.00", "count": 25},
        ],
        "evaluations": [
            {
                "dataset": "solar-demo-v3",
                "date": "2026-07-05",
                "precision": 0.91,
                "recall": 0.88,
                "synthetic": True,
            },
            {
                "dataset": "solar-hard-negatives-v2",
                "date": "2026-06-28",
                "precision": 0.89,
                "recall": 0.86,
                "synthetic": True,
            },
        ],
    }


@app.post("/api/v1/models/{model_id}/deploy")
@app.post("/api/models/{model_id}/deploy")
def deploy_model(
    model_id: str,
    request: Request,
    ctx: Context = Depends(require("model:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    model = db.get(ModelVersion, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model version not found.")
    model.state = "Staged"
    model.updated_at = now()
    audit(
        db,
        ctx,
        request,
        "Staged model deployment simulation",
        "model",
        model.id,
        workflow="Data Scientist → Inspection Manager → Organization Admin",
    )
    db.commit()
    return {
        "id": model.id,
        "state": model.state,
        "notice": "Staged deployment is a governed simulation; no device binary was updated.",
    }


@app.get("/api/v1/datasets")
def datasets(
    ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> list[dict[str, Any]]:
    return [
        {
            "id": x.id,
            "name": x.name,
            "source": x.source,
            "image_count": x.image_count,
            "annotation_count": x.annotation_count,
            "summary": x.summary,
        }
        for x in db.scalars(
            select(DatasetVersion).where(DatasetVersion.organization_id == ctx.organization_id)
        ).all()
    ]


@app.get("/api/v1/alerts")
def alerts(ctx: Context = Depends(get_context), db: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [
        {
            "id": a.id,
            "category": a.category,
            "severity": a.severity,
            "state": a.state,
            "title": a.title,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "detail": a.detail,
            "created_at": a.created_at.isoformat(),
        }
        for a in db.scalars(
            select(Alert)
            .where(Alert.organization_id == ctx.organization_id)
            .order_by(desc(Alert.created_at))
        ).all()
    ]


@app.post("/api/v1/alerts/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: str,
    request: Request,
    ctx: Context = Depends(require("read")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    alert = org_item(db, Alert, alert_id, ctx)
    alert.state = "Acknowledged"
    alert.updated_at = now()
    audit(db, ctx, request, "Acknowledged alert", "alert", alert.id)
    db.commit()
    return {"id": alert.id, "state": alert.state}


@app.get("/api/v1/quality")
def quality_center(
    ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> dict[str, Any]:
    media = db.scalars(select(MediaFile).where(MediaFile.organization_id == ctx.organization_id)).all()
    findings = db.scalars(select(Finding).where(Finding.organization_id == ctx.organization_id)).all()
    issues = []
    for m in media:
        for warning in (m.validation or {}).get("warnings", []) + (m.quality or {}).get("warnings", []):
            issues.append(
                {
                    "type": "Capture quality",
                    "severity": "Warning",
                    "media_id": m.id,
                    "detail": warning,
                    "suggested_remediation": "Review or schedule a follow-up capture.",
                }
            )
    pending = sum(1 for f in findings if f.review_state in {"pending", "uncertain"})
    if pending:
        issues.append(
            {
                "type": "Reviewer backlog",
                "severity": "Warning" if pending < 20 else "Critical",
                "detail": f"{pending} findings require attention",
                "suggested_remediation": "Assign reviewers or escalate the review SLA.",
            }
        )
    return {
        "overall_score": max(45, 92 - min(35, len(issues))),
        "capture_quality": 88,
        "coverage_quality": 82,
        "metadata_completeness": 94,
        "review_backlog": pending,
        "evidence_completeness": 97,
        "issues": issues[:25],
        "notice": "Inspection data quality is distinct from model quality. Scores are synthetic demo indicators.",
    }


def audit_out(e: AuditEvent) -> dict[str, Any]:
    return {
        "id": e.id,
        "at": e.occurred_at.isoformat(),
        "actor": e.actor_name,
        "action": e.action,
        "target": f"{e.target_type}:{e.target_id}",
        "metadata": e.metadata_json,
    }


@app.get("/api/v1/governance/audit")
def governance_audit(
    ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> list[dict[str, Any]]:
    return [
        audit_out(x)
        for x in db.scalars(
            select(AuditEvent)
            .where(AuditEvent.organization_id == ctx.organization_id)
            .order_by(desc(AuditEvent.occurred_at))
            .limit(200)
        ).all()
    ]


@app.post("/api/v1/governance/api-keys")
def create_api_key(
    body: ApiKeyRequest,
    request: Request,
    ctx: Context = Depends(require("model:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    secret = issue_token("fsk")
    key = APIKey(
        id=make_id("key"),
        organization_id=ctx.organization_id,
        name=body.name,
        key_prefix=secret[:12],
        secret_hash=hash_secret(secret),
        scopes=body.scopes,
        expires_at=now() + timedelta(days=body.expires_days),
        revoked_at=None,
        created_at=now(),
        updated_at=now(),
    )
    db.add(key)
    audit(db, ctx, request, "Created scoped API key", "api_key", key.id, scopes=body.scopes)
    db.commit()
    return {
        "id": key.id,
        "name": key.name,
        "prefix": key.key_prefix,
        "scopes": key.scopes,
        "expires_at": key.expires_at.isoformat(),
        "secret": secret,
        "warning": "Copy this secret now; it is not returned again.",
    }


@app.get("/api/v1/webhooks/deliveries")
def webhook_deliveries(
    ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> list[dict[str, Any]]:
    return [
        {
            "id": x.id,
            "event_type": x.event_type,
            "target_url": x.target_url,
            "state": x.state,
            "attempts": x.attempts,
            "payload": x.payload,
        }
        for x in db.scalars(
            select(WebhookDelivery).where(WebhookDelivery.organization_id == ctx.organization_id)
        ).all()
    ]


# Governed intelligence assistant
@app.post("/api/v1/assistant/insights")
def assistant_insight(
    body: AssistantRequest,
    request: Request,
    ctx: Context = Depends(get_context),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    question = body.question.lower()
    findings = db.scalars(select(Finding).where(Finding.organization_id == ctx.organization_id)).all()
    devices = db.scalars(select(Device).where(Device.organization_id == ctx.organization_id)).all()
    alerts_rows = db.scalars(
        select(Alert).where(Alert.organization_id == ctx.organization_id, Alert.state == "Open")
    ).all()
    if any(x in question for x in ["site", "attention", "today"]):
        summary = f"{sum(1 for f in findings if f.severity in {'critical', 'high'} and f.review_state != 'rejected')} high-priority findings and {len(alerts_rows)} open alerts need attention in this workspace."
        evidence = [finding_out(x, db) for x in findings if x.severity in {"critical", "high"}][:5]
    elif any(x in question for x in ["device", "sync", "queue"]):
        queued = [device_out(x, db) for x in devices if (x.health or {}).get("queue_count", 0) > 0]
        summary = f"{len(queued)} devices have pending or degraded sync state."
        evidence = queued
    elif any(x in question for x in ["risk", "critical"]):
        risks = risk_center(ctx, db)["high_risk_assets"]
        summary = "Risk is elevated where evidence-linked findings, open maintenance work, freshness, and quality warnings compound."
        evidence = risks[:5]
    else:
        summary = "The governed assistant supports inspection priorities, risk drivers, review backlog, device queues, work-order SLA context, coverage, and model correction trend summaries."
        evidence = []
    audit(
        db,
        ctx,
        request,
        "Generated governed inspection insight",
        "assistant",
        "insight",
        mode=body.mode,
        question=body.question,
    )
    db.commit()
    return {
        "summary": summary,
        "scope": compact_org(db.get(Organization, ctx.organization_id)),
        "data_used": ["projects", "findings", "devices", "alerts", "asset-risk snapshots"],
        "filters_used": {"workspace": ctx.organization_id},
        "supporting_evidence": evidence,
        "data_quality_notices": ["Synthetic demo data; deterministic local logic."],
        "confidence": "medium",
        "limitations": "No generative model or unsupported external data access is used. Draft actions require confirmation before persistence.",
        "suggested_next_action": "Open the related entity and assign an owner or create a draft work order.",
    }


# Reporting
@app.get("/api/v1/reports/preview")
@app.get("/api/reports/preview")
def report_preview(
    ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> dict[str, Any]:
    project = db.scalar(select(Project).where(Project.organization_id == ctx.organization_id).limit(1))
    findings = db.scalars(
        select(Finding)
        .where(Finding.organization_id == ctx.organization_id)
        .order_by(desc(Finding.created_at))
        .limit(4)
    ).all()
    works = db.scalars(select(WorkOrder).where(WorkOrder.organization_id == ctx.organization_id)).all()
    assets = (
        db.scalar(
            select(func.count()).select_from(Asset).where(Asset.organization_id == ctx.organization_id)
        )
        or 0
    )
    return {
        "title": f"{project.name if project else 'FieldSight'} — Inspection Report",
        "summary": "Evidence-first executive summary generated from persistent demo records. Critical issues remain human-confirmation and approval gated.",
        "statistics": {
            "assets": assets,
            "media": db.scalar(
                select(func.count())
                .select_from(MediaFile)
                .where(MediaFile.organization_id == ctx.organization_id)
            )
            or 0,
            "detections": db.scalar(
                select(func.count())
                .select_from(Finding)
                .where(Finding.organization_id == ctx.organization_id)
            )
            or 0,
            "verified": sum(1 for x in findings if x.review_state == "verified"),
            "critical": sum(1 for x in findings if x.severity == "critical"),
            "work_orders": len(works),
        },
        "recommendations": [
            "Prioritize verified critical evidence before dispatch.",
            "Resolve pending review backlog before report sign-off.",
            "Schedule a verification inspection after maintenance closure.",
        ],
        "findings": [finding_out(x, db) for x in findings],
    }


@app.post("/api/v1/reports")
@app.post("/api/reports")
def create_report(
    body: ReportRequest,
    request: Request,
    ctx: Context = Depends(require("report:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    project = org_item(db, Project, body.project_id, ctx)
    report = Report(
        id=make_id("report"),
        organization_id=ctx.organization_id,
        project_id=project.id,
        title=body.title,
        state="Generated",
        template=body.template,
        scope={"project_id": project.id, "synthetic": True},
        export_key=None,
        created_at=now(),
        updated_at=now(),
    )
    db.add(report)
    audit(db, ctx, request, "Generated inspection report", "report", report.id, template=body.template)
    db.commit()
    return {
        "id": report.id,
        "title": report.title,
        "state": report.state,
        "preview": report_preview(ctx, db),
    }


def build_pdf(ctx: Context, db: Session) -> bytes:
    preview = report_preview(ctx, db)
    buff = io.BytesIO()
    c = canvas.Canvas(buff, pagesize=A4)
    w, h = A4
    c.setFillColor(colors.HexColor("#102027"))
    c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#F0F3ED"))
    c.setFont("Helvetica-Bold", 19)
    c.drawString(46, h - 58, "FIELDSIGHT EDGE")
    c.setFillColor(colors.HexColor("#FF8B2C"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(46, h - 75, "INSPECTION REPORT · SYNTHETIC DEMO")
    c.setFillColor(colors.HexColor("#F0F3ED"))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(46, h - 118, preview["title"][:72])
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#C2D0CB"))
    text = c.beginText(46, h - 145)
    text.setLeading(15)
    for line in preview["summary"].split(". "):
        text.textLine(line)
    c.drawText(text)
    y = h - 205
    c.setFillColor(colors.HexColor("#FF8B2C"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(46, y, "EXECUTIVE METRICS")
    y -= 25
    c.setFillColor(colors.HexColor("#F0F3ED"))
    c.setFont("Helvetica", 10)
    for k, v in preview["statistics"].items():
        c.drawString(54, y, f"{k.replace('_', ' ').title()}: {v}")
        y -= 16
    y -= 10
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#FF8B2C"))
    c.drawString(46, y, "PRIORITY FINDINGS")
    y -= 22
    c.setFillColor(colors.HexColor("#F0F3ED"))
    c.setFont("Helvetica", 10)
    for f in preview["findings"][:3]:
        c.drawString(
            54, y, f"• {f['label']} · {f['severity'].upper()} · {int(f['confidence'] * 100)}% confidence"
        )
        y -= 17
    y -= 10
    c.setFillColor(colors.HexColor("#FF8B2C"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(46, y, "RECOMMENDATIONS")
    y -= 22
    c.setFillColor(colors.HexColor("#F0F3ED"))
    c.setFont("Helvetica", 10)
    for r in preview["recommendations"]:
        c.drawString(54, y, f"• {r}")
        y -= 17
    c.setFillColor(colors.HexColor("#94A3A5"))
    c.setFont("Helvetica", 8)
    c.drawString(
        46, 42, "FieldSight Edge · Persistent deterministic demo · No real-world inspection accuracy claim"
    )
    c.save()
    return buff.getvalue()


@app.get("/api/v1/reports/export.pdf")
@app.get("/api/reports/export.pdf")
def export_report(
    request: Request, ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> StreamingResponse:
    pdf = build_pdf(ctx, db)
    audit(db, ctx, request, "Downloaded report export", "report", "on-demand", format="pdf")
    db.commit()
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=fieldsight-inspection-report.pdf"},
    )


@app.get("/api/media/{media_id}/preview.svg")
@app.get("/api/v1/media/{media_id}/preview.svg")
def media_preview(
    media_id: str, ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> Response:
    media = org_item(db, MediaFile, media_id, ctx)
    f = db.scalar(select(Finding).where(Finding.media_id == media.id).order_by(desc(Finding.created_at)))
    label = (
        TAXONOMY.get(f.defect_class, {}).get("label", "Inspection capture") if f else "Inspection capture"
    )
    bbox = f.bbox if f else {"x": 25, "y": 28, "w": 34, "h": 24}
    color = {"critical": "#ff7a45", "high": "#ffae42", "medium": "#e6c051", "low": "#97b26a"}.get(
        f.severity if f else "low", "#97b26a"
    )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 420"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#536b42"/><stop offset="1" stop-color="#1b2e35"/></linearGradient><pattern id="p" width="36" height="20" patternUnits="userSpaceOnUse"><path d="M0 1H36M1 0V20" stroke="#dae4c8" stroke-opacity=".24"/></pattern></defs><rect width="680" height="420" fill="url(#g)"/><rect x="62" y="45" width="555" height="320" rx="4" fill="url(#p)" transform="rotate(-8 340 210)"/><path d="M80 335 C210 275 280 330 390 245 S560 190 640 118" fill="none" stroke="#c7db80" stroke-width="3" stroke-dasharray="8 8"/><rect x="{bbox["x"] * 6}" y="{bbox["y"] * 5}" width="{bbox["w"] * 6}" height="{bbox["h"] * 5}" fill="none" stroke="{color}" stroke-width="5"/><rect x="{bbox["x"] * 6}" y="{bbox["y"] * 5 - 30}" width="192" height="27" rx="3" fill="{color}"/><text x="{bbox["x"] * 6 + 8}" y="{bbox["y"] * 5 - 11}" fill="#172024" font-family="Arial" font-size="14" font-weight="bold">{label}</text><text x="24" y="397" fill="#f0f3ed" font-family="monospace" font-size="12">SYNTHETIC EVIDENCE · {media.id} · {media.captured_at.date().isoformat()}</text></svg>'''
    return Response(svg, media_type="image/svg+xml")

# ---------------------------------------------------------------------------
# Phase 3 launch-hardening routes. These routes intentionally operate on the
# same persistent Phase 2 records; they are not frontend-only simulations.
# ---------------------------------------------------------------------------

MISSION_TRANSITIONS: dict[str, set[str]] = {
    "Draft": {"Planned", "Cancelled"},
    "Planned": {"Assigned", "Blocked", "Cancelled"},
    "Assigned": {"In progress", "Blocked", "Cancelled"},
    "In progress": {"Captured", "Blocked", "Cancelled"},
    "Captured": {"Uploading", "Processing", "Under review"},
    "Uploading": {"Processing", "Blocked"},
    "Processing": {"Under review", "Blocked"},
    "Under review": {"Completed", "Blocked"},
    "Blocked": {"Planned", "Assigned", "Cancelled"},
    "Completed": set(),
    "Cancelled": set(),
}


class MissionUpdateRequest(BaseModel):
    state: str | None = None
    assigned_operator: str | None = None
    assigned_device_id: str | None = None
    checklist: list[dict[str, Any]] | None = None
    safety_note: str | None = None
    due_date: str | None = None


class WorkOrderUpdateRequest(BaseModel):
    assignee: str | None = None
    note: str | None = None
    estimated_cost: int | None = None
    evidence_note: str | None = None


class AlertUpdateRequest(BaseModel):
    assignee: str | None = None
    snooze_hours: int = Field(default=24, ge=1, le=720)
    resolution_note: str = ""


class WatchlistRequest(BaseModel):
    name: str
    description: str = ""
    category: str = "Operational"


class WatchlistItemRequest(BaseModel):
    entity_type: str = Field(pattern="^(asset|device|mission|finding|defect|work_order|alert)$")
    entity_id: str
    note: str = ""


class ModelCandidateRequest(BaseModel):
    name: str
    version: str
    dataset_id: str
    release_notes: str = ""


class DeploymentRequest(BaseModel):
    target: str = "cloud-profile:default"


class ScheduleRequest(BaseModel):
    name: str
    project_id: str | None = None
    template: str = "executive"
    frequency: str = Field(default="weekly", pattern="^(daily|weekly|monthly)$")


class DeletionRequestBody(BaseModel):
    request_key: str
    scope: dict[str, Any] = {}
    reason: str = ""


def _phase3_model_out(model: ModelVersion, db: Session) -> dict[str, Any]:
    evaluations = db.scalars(select(ModelEvaluation).where(ModelEvaluation.model_version_id == model.id)).all()
    deployments = db.scalars(select(ModelDeployment).where(ModelDeployment.model_version_id == model.id)).all()
    return {
        "id": model.id,
        "name": model.name,
        "version": model.version,
        "state": model.state,
        "model_family": model.model_family,
        "task_type": model.task_type,
        "runtime": model.runtime,
        "metrics": model.metrics,
        "model_card": model.model_card,
        "evaluations": [
            {"id": e.id, "state": e.state, "metrics": e.metrics, "recommendation": e.recommendation, "synthetic": e.synthetic}
            for e in evaluations
        ],
        "deployments": [
            {"id": d.id, "target": d.target, "state": d.state, "approval_history": d.approval_history, "rollout": d.rollout}
            for d in deployments
        ],
        "synthetic_notice": "Synthetic evaluation data for demo and workflow validation.",
    }


def _assert_entity_scope(db: Session, entity_type: str, entity_id: str, ctx: Context) -> None:
    models: dict[str, type] = {
        "asset": Asset, "device": Device, "mission": Mission, "finding": Finding,
        "defect": Defect, "work_order": WorkOrder, "alert": Alert,
    }
    model = models.get(entity_type)
    if not model:
        raise HTTPException(status_code=422, detail="Unsupported watchlist entity type.")
    org_item(db, model, entity_id, ctx)


@app.get("/api/v1/operations/health")
def operations_health(ctx: Context = Depends(get_context), db: Session = Depends(get_session)) -> dict[str, Any]:
    db_health = database_status()
    queued = db.scalar(select(func.count()).select_from(InferenceJob).where(InferenceJob.organization_id == ctx.organization_id, InferenceJob.state.in_(["Queued", "Preparing", "Running", "Retrying"]))) or 0
    sync_pending = db.scalar(select(func.count()).select_from(SyncJob).where(SyncJob.organization_id == ctx.organization_id, SyncJob.state != "Synchronized")) or 0
    return {
        "api": "healthy",
        "database": db_health,
        "worker": {"state": "inline-demo" if SETTINGS.worker_mode == "inline" else "external-boundary", "queued_inference": queued},
        "object_storage": {"state": "local-filesystem", "configured": True},
        "edge_sync": {"pending": sync_pending, "state": "healthy" if sync_pending < 10 else "delayed"},
        "mode": "persistent deterministic local demo" if SETTINGS.demo_mode else "configured deployment mode",
        "last_migration": "20260707_02",
    }


@app.patch("/api/v1/missions/{mission_id}")
def update_mission_phase3(
    mission_id: str,
    body: MissionUpdateRequest,
    request: Request,
    ctx: Context = Depends(require("mission:write")),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    mission = org_item(db, Mission, mission_id, ctx)
    if body.state and body.state != mission.state:
        allowed = MISSION_TRANSITIONS.get(mission.state, set())
        if body.state not in allowed:
            raise HTTPException(status_code=422, detail=f"Mission cannot transition from {mission.state} to {body.state}.")
        mission.state = body.state
    if body.assigned_device_id:
        org_item(db, Device, body.assigned_device_id, ctx)
        mission.assigned_device_id = body.assigned_device_id
    if body.assigned_operator is not None:
        mission.assigned_operator = body.assigned_operator
    if body.checklist is not None:
        mission.checklist = body.checklist
    if body.safety_note is not None:
        mission.settings = {**(mission.settings or {}), "safety_note": body.safety_note}
    if body.due_date is not None:
        mission.due_date = body.due_date
    mission.updated_at = now()
    audit(db, ctx, request, "Updated mission operational state", "mission", mission.id, state=mission.state)
    db.commit()
    return mission_out(mission, db) | {"audit_event": "Mission update recorded", "next_actions": ["capture", "upload", "request review"]}


@app.get("/api/v1/findings/{finding_id}")
def finding_detail_phase3(
    finding_id: str, ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> dict[str, Any]:
    finding = org_item(db, Finding, finding_id, ctx)
    audits = db.scalars(select(AuditEvent).where(AuditEvent.organization_id == ctx.organization_id, AuditEvent.target_id == finding.id).order_by(desc(AuditEvent.occurred_at))).all()
    defect = db.scalar(select(Defect).where(Defect.finding_id == finding.id))
    return finding_out(finding, db) | {
        "defect": {"id": defect.id, "state": defect.state, "severity": defect.severity} if defect else None,
        "audit": [audit_out(x) for x in audits[:25]],
        "evidence_lineage": f"/api/v1/media/{finding.media_id}/lineage",
        "decision_boundary": "Human reviewer decisions are stored separately from immutable detector output.",
    }


@app.post("/api/v1/findings/{finding_id}/defects")
def create_defect_phase3(
    finding_id: str, request: Request, ctx: Context = Depends(require("review:write")), db: Session = Depends(get_session)
) -> dict[str, Any]:
    finding = org_item(db, Finding, finding_id, ctx)
    if finding.review_state != "verified" or not finding.asset_id:
        raise HTTPException(status_code=422, detail="Only a verified finding linked to an asset can create a defect.")
    defect = db.scalar(select(Defect).where(Defect.finding_id == finding.id))
    if not defect:
        defect = Defect(
            id=make_id("defect"), organization_id=ctx.organization_id, asset_id=finding.asset_id,
            finding_id=finding.id, title=f"Verified {finding.defect_class.replace('_', ' ')}",
            state="Verified", severity=finding.severity, created_at=now(), updated_at=now(),
        )
        db.add(defect)
        audit(db, ctx, request, "Created verified defect", "defect", defect.id, finding_id=finding.id)
        db.commit()
    return {"id": defect.id, "finding_id": defect.finding_id, "asset_id": defect.asset_id, "state": defect.state, "severity": defect.severity}


@app.get("/api/v1/work-orders/{work_order_id}")
def work_order_detail_phase3(
    work_order_id: str, ctx: Context = Depends(get_context), db: Session = Depends(get_session)
) -> dict[str, Any]:
    work = org_item(db, WorkOrder, work_order_id, ctx)
    audit_rows = db.scalars(select(AuditEvent).where(AuditEvent.organization_id == ctx.organization_id, AuditEvent.target_id == work.id).order_by(desc(AuditEvent.occurred_at))).all()
    return work_order_out(work) | {"audit": [audit_out(x) for x in audit_rows[:30]], "verification_required": work.status in {"Verification required", "Completed"}, "synthetic_cost_notice": "Estimated cost is synthetic demo planning context."}


@app.post("/api/v1/work-orders/{work_order_id}/submit")
def submit_work_order_phase3(
    work_order_id: str, request: Request, ctx: Context = Depends(require("workorder:write")), db: Session = Depends(get_session)
) -> dict[str, Any]:
    work = org_item(db, WorkOrder, work_order_id, ctx)
    if work.status not in {"Draft", "Awaiting approval"}:
        raise HTTPException(status_code=422, detail="Only draft work orders can be submitted for approval.")
    work.status = "Awaiting approval"
    work.updated_at = now()
    audit(db, ctx, request, "Submitted work order for approval", "work_order", work.id)
    db.commit()
    return work_order_out(work) | {"next_action": "Organization Admin approval required for critical or high-cost work."}


@app.post("/api/v1/work-orders/{work_order_id}/reject")
def reject_work_order_phase3(
    work_order_id: str, body: WorkOrderUpdateRequest, request: Request, ctx: Context = Depends(require("workorder:write")), db: Session = Depends(get_session)
) -> dict[str, Any]:
    work = org_item(db, WorkOrder, work_order_id, ctx)
    if work.status not in {"Draft", "Awaiting approval"}:
        raise HTTPException(status_code=422, detail="Work order is not awaiting approval.")
    work.status = "Draft"
    work.approval_history = [*(work.approval_history or []), {"at": now().isoformat(), "by": ctx.user_name, "decision": "rejected", "note": body.note or ""}]
    work.updated_at = now()
    audit(db, ctx, request, "Rejected work order approval", "work_order", work.id, note=body.note or "")
    db.commit()
    return work_order_out(work)


@app.post("/api/v1/work-orders/{work_order_id}/assign")
def assign_work_order_phase3(
    work_order_id: str, body: WorkOrderUpdateRequest, request: Request, ctx: Context = Depends(require("workorder:write")), db: Session = Depends(get_session)
) -> dict[str, Any]:
    work = org_item(db, WorkOrder, work_order_id, ctx)
    if work.status not in {"Approved", "Assigned", "In progress"}:
        raise HTTPException(status_code=422, detail="Approval is required before technician assignment.")
    work.assignee = body.assignee or "Unassigned"
    work.status = "Assigned" if work.assignee != "Unassigned" else work.status
    work.updated_at = now()
    audit(db, ctx, request, "Assigned work order", "work_order", work.id, assignee=work.assignee)
    db.commit()
    return work_order_out(work)


@app.post("/api/v1/work-orders/{work_order_id}/resolution-evidence")
def work_order_evidence_phase3(
    work_order_id: str, body: WorkOrderUpdateRequest, request: Request, ctx: Context = Depends(require("workorder:write")), db: Session = Depends(get_session)
) -> dict[str, Any]:
    work = org_item(db, WorkOrder, work_order_id, ctx)
    if work.status not in {"Approved", "Assigned", "In progress", "Waiting for parts", "Waiting for access", "Verification required"}:
        raise HTTPException(status_code=422, detail="Resolution evidence cannot be attached before work is approved.")
    evidence = {"at": now().isoformat(), "by": ctx.user_name, "note": body.evidence_note or "Synthetic resolution evidence", "synthetic": True}
    work.resolution_evidence = [*(work.resolution_evidence or []), evidence]
    work.status = "Verification required"
    work.updated_at = now()
    audit(db, ctx, request, "Attached resolution evidence", "work_order", work.id)
    db.commit()
    return work_order_out(work) | {"next_action": "Request a verification inspection and reviewer decision."}


@app.post("/api/v1/work-orders/{work_order_id}/close")
def close_work_order_phase3(
    work_order_id: str, request: Request, ctx: Context = Depends(require("review:write")), db: Session = Depends(get_session)
) -> dict[str, Any]:
    work = org_item(db, WorkOrder, work_order_id, ctx)
    if work.status != "Verified":
        raise HTTPException(status_code=422, detail="A verified resolution is required before closure.")
    work.status = "Closed"
    work.updated_at = now()
    audit(db, ctx, request, "Closed verified work order", "work_order", work.id)
    db.commit()
    return work_order_out(work)


@app.post("/api/v1/alerts/{alert_id}/assign")
def assign_alert_phase3(alert_id: str, body: AlertUpdateRequest, request: Request, ctx: Context = Depends(require("read")), db: Session = Depends(get_session)) -> dict[str, Any]:
    alert = org_item(db, Alert, alert_id, ctx)
    alert.state = "Assigned"
    alert.detail = {**(alert.detail or {}), "assignee": body.assignee or "Unassigned"}
    alert.updated_at = now()
    audit(db, ctx, request, "Assigned alert", "alert", alert.id, assignee=body.assignee)
    db.commit()
    return {"id": alert.id, "state": alert.state, "detail": alert.detail}


@app.post("/api/v1/alerts/{alert_id}/snooze")
def snooze_alert_phase3(alert_id: str, body: AlertUpdateRequest, request: Request, ctx: Context = Depends(require("read")), db: Session = Depends(get_session)) -> dict[str, Any]:
    alert = org_item(db, Alert, alert_id, ctx)
    alert.state = "Snoozed"
    alert.detail = {**(alert.detail or {}), "snoozed_until": (now() + timedelta(hours=body.snooze_hours)).isoformat()}
    alert.updated_at = now()
    audit(db, ctx, request, "Snoozed alert", "alert", alert.id, hours=body.snooze_hours)
    db.commit()
    return {"id": alert.id, "state": alert.state, "detail": alert.detail}


@app.post("/api/v1/alerts/{alert_id}/resolve")
def resolve_alert_phase3(alert_id: str, body: AlertUpdateRequest, request: Request, ctx: Context = Depends(require("read")), db: Session = Depends(get_session)) -> dict[str, Any]:
    alert = org_item(db, Alert, alert_id, ctx)
    alert.state = "Resolved"
    alert.detail = {**(alert.detail or {}), "resolution_note": body.resolution_note}
    alert.updated_at = now()
    audit(db, ctx, request, "Resolved alert", "alert", alert.id, resolution_note=body.resolution_note)
    db.commit()
    return {"id": alert.id, "state": alert.state, "detail": alert.detail}


@app.get("/api/v1/watchlists")
def list_watchlists_phase3(ctx: Context = Depends(get_context), db: Session = Depends(get_session)) -> list[dict[str, Any]]:
    rows = db.scalars(select(Watchlist).where(Watchlist.organization_id == ctx.organization_id).order_by(desc(Watchlist.created_at))).all()
    output = []
    for row in rows:
        items = db.scalars(select(WatchlistItem).where(WatchlistItem.watchlist_id == row.id, WatchlistItem.organization_id == ctx.organization_id)).all()
        output.append({"id": row.id, "name": row.name, "description": row.description, "category": row.category, "item_count": len(items), "items": [{"id": item.id, "entity_type": item.entity_type, "entity_id": item.entity_id, "note": item.note} for item in items]})
    return output


@app.post("/api/v1/watchlists")
def create_watchlist_phase3(body: WatchlistRequest, request: Request, ctx: Context = Depends(require("read")), db: Session = Depends(get_session)) -> dict[str, Any]:
    existing = db.scalar(select(Watchlist).where(Watchlist.organization_id == ctx.organization_id, Watchlist.name == body.name))
    if existing:
        return {"id": existing.id, "name": existing.name, "duplicate": True}
    row = Watchlist(id=make_id("watch"), organization_id=ctx.organization_id, name=body.name, description=body.description, category=body.category, created_by=ctx.user_id, created_at=now(), updated_at=now())
    db.add(row)
    audit(db, ctx, request, "Created watchlist", "watchlist", row.id, category=body.category)
    db.commit()
    return {"id": row.id, "name": row.name, "description": row.description, "category": row.category, "duplicate": False}


@app.post("/api/v1/watchlists/{watchlist_id}/items")
def add_watchlist_item_phase3(watchlist_id: str, body: WatchlistItemRequest, request: Request, ctx: Context = Depends(require("read")), db: Session = Depends(get_session)) -> dict[str, Any]:
    watchlist = org_item(db, Watchlist, watchlist_id, ctx)
    _assert_entity_scope(db, body.entity_type, body.entity_id, ctx)
    existing = db.scalar(select(WatchlistItem).where(WatchlistItem.organization_id == ctx.organization_id, WatchlistItem.watchlist_id == watchlist.id, WatchlistItem.entity_type == body.entity_type, WatchlistItem.entity_id == body.entity_id))
    if existing:
        return {"id": existing.id, "duplicate": True}
    item = WatchlistItem(id=make_id("watchitem"), organization_id=ctx.organization_id, watchlist_id=watchlist.id, entity_type=body.entity_type, entity_id=body.entity_id, note=body.note, created_at=now(), updated_at=now())
    db.add(item)
    audit(db, ctx, request, "Added watchlist item", "watchlist", watchlist.id, entity_type=body.entity_type, entity_id=body.entity_id)
    db.commit()
    return {"id": item.id, "duplicate": False, "watchlist_id": watchlist.id}


@app.delete("/api/v1/watchlists/{watchlist_id}/items/{item_id}")
def remove_watchlist_item_phase3(watchlist_id: str, item_id: str, request: Request, ctx: Context = Depends(require("read")), db: Session = Depends(get_session)) -> dict[str, Any]:
    watchlist = org_item(db, Watchlist, watchlist_id, ctx)
    item = org_item(db, WatchlistItem, item_id, ctx)
    if item.watchlist_id != watchlist.id:
        raise HTTPException(status_code=404, detail="Watchlist item not found.")
    db.delete(item)
    audit(db, ctx, request, "Removed watchlist item", "watchlist", watchlist.id, item_id=item_id)
    db.commit()
    return {"ok": True}


@app.post("/api/v1/findings/{finding_id}/dataset-candidate")
def dataset_candidate_phase3(finding_id: str, request: Request, ctx: Context = Depends(require("review:write")), db: Session = Depends(get_session)) -> dict[str, Any]:
    finding = org_item(db, Finding, finding_id, ctx)
    existing = db.scalar(select(DatasetCandidate).where(DatasetCandidate.organization_id == ctx.organization_id, DatasetCandidate.finding_id == finding.id))
    if existing:
        return {"id": existing.id, "state": existing.state, "duplicate": True}
    finding.training_candidate = True
    candidate = DatasetCandidate(id=make_id("candidate"), organization_id=ctx.organization_id, finding_id=finding.id, state="Candidate", rationale="Reviewer-approved active-learning candidate", reviewer_id=ctx.user_id, created_at=now(), updated_at=now())
    db.add(candidate)
    audit(db, ctx, request, "Marked finding as dataset candidate", "finding", finding.id, candidate_id=candidate.id)
    db.commit()
    return {"id": candidate.id, "state": candidate.state, "finding_id": candidate.finding_id, "duplicate": False}


@app.post("/api/v1/models/candidates")
def create_model_candidate_phase3(body: ModelCandidateRequest, request: Request, ctx: Context = Depends(require("model:write")), db: Session = Depends(get_session)) -> dict[str, Any]:
    dataset = org_item(db, DatasetVersion, body.dataset_id, ctx)
    model = ModelVersion(id=make_id("model"), organization_id=ctx.organization_id, name=body.name, version=body.version, state="Candidate", model_family="YOLO-compatible adapter boundary", task_type="object-detection", runtime="deterministic local provider", metrics={"precision_proxy": 0.89, "recall_proxy": 0.86, "note": "Synthetic evaluation data for demo and workflow validation."}, model_card={"release_notes": body.release_notes, "dataset_id": dataset.id, "limitations": "No model weights are bundled or downloaded."}, created_at=now(), updated_at=now())
    db.add(model)
    audit(db, ctx, request, "Created model candidate", "model", model.id, dataset_id=dataset.id)
    db.commit()
    return _phase3_model_out(model, db)


@app.post("/api/v1/models/{model_id}/evaluations")
def evaluate_model_phase3(model_id: str, request: Request, ctx: Context = Depends(require("model:write")), db: Session = Depends(get_session)) -> dict[str, Any]:
    model = org_item(db, ModelVersion, model_id, ctx)
    dataset = db.scalar(select(DatasetVersion).where(DatasetVersion.organization_id == ctx.organization_id).order_by(desc(DatasetVersion.created_at)))
    if not dataset:
        raise HTTPException(status_code=422, detail="A workspace dataset is required for evaluation.")
    evaluation = db.scalar(select(ModelEvaluation).where(ModelEvaluation.organization_id == ctx.organization_id, ModelEvaluation.model_version_id == model.id, ModelEvaluation.dataset_version_id == dataset.id))
    if not evaluation:
        evaluation = ModelEvaluation(id=make_id("eval"), organization_id=ctx.organization_id, model_version_id=model.id, dataset_version_id=dataset.id, state="Completed", metrics={"precision_proxy": 0.90, "recall_proxy": 0.87, "f1_proxy": 0.885, "latency_ms_p95": 146, "synthetic": True}, recommendation="Eligible for governed review", synthetic=True, created_at=now(), updated_at=now())
        db.add(evaluation)
    model.state = "Validating"
    model.updated_at = now()
    audit(db, ctx, request, "Ran synthetic model evaluation", "model", model.id, evaluation_id=evaluation.id)
    db.commit()
    return _phase3_model_out(model, db)


@app.post("/api/v1/models/{model_id}/deployment-requests")
def model_deploy_request_phase3(model_id: str, body: DeploymentRequest, request: Request, ctx: Context = Depends(require("model:write")), db: Session = Depends(get_session)) -> dict[str, Any]:
    model = org_item(db, ModelVersion, model_id, ctx)
    if model.state not in {"Candidate", "Validating", "Approved", "Staged"}:
        raise HTTPException(status_code=422, detail="Model is not eligible for deployment request.")
    deployment = db.scalar(select(ModelDeployment).where(ModelDeployment.organization_id == ctx.organization_id, ModelDeployment.model_version_id == model.id, ModelDeployment.target == body.target))
    if not deployment:
        deployment = ModelDeployment(id=make_id("deploy"), organization_id=ctx.organization_id, model_version_id=model.id, target=body.target, state="Awaiting approval", approval_history=[], rollout={"simulation": True, "device_binary_updated": False}, created_at=now(), updated_at=now())
        db.add(deployment)
    audit(db, ctx, request, "Submitted staged model deployment request", "model_deployment", deployment.id, model_id=model.id, target=body.target)
    db.commit()
    return {"id": deployment.id, "state": deployment.state, "target": deployment.target, "notice": "This is a staged simulation; no physical edge device was updated."}


@app.post("/api/v1/model-deployments/{deployment_id}/approve")
def approve_deployment_phase3(deployment_id: str, request: Request, ctx: Context = Depends(require_model_approval), db: Session = Depends(get_session)) -> dict[str, Any]:
    deployment = org_item(db, ModelDeployment, deployment_id, ctx)
    if deployment.state != "Awaiting approval":
        raise HTTPException(status_code=422, detail="Deployment is not awaiting approval.")
    deployment.state = "Staged"
    deployment.approval_history = [*(deployment.approval_history or []), {"at": now().isoformat(), "by": ctx.user_name, "decision": "approved", "simulation": True}]
    deployment.updated_at = now()
    model = db.get(ModelVersion, deployment.model_version_id)
    if model:
        model.state = "Staged"
        model.updated_at = now()
    audit(db, ctx, request, "Approved staged model deployment", "model_deployment", deployment.id, target=deployment.target)
    db.commit()
    return {"id": deployment.id, "state": deployment.state, "notice": "Staged deployment simulation completed; no physical edge device was changed and provider configuration is still required for actual rollout."}


@app.post("/api/v1/model-deployments/{deployment_id}/rollback")
def rollback_deployment_phase3(deployment_id: str, request: Request, ctx: Context = Depends(require("model:write")), db: Session = Depends(get_session)) -> dict[str, Any]:
    deployment = org_item(db, ModelDeployment, deployment_id, ctx)
    deployment.state = "Rolled back"
    deployment.approval_history = [*(deployment.approval_history or []), {"at": now().isoformat(), "by": ctx.user_name, "decision": "rollback", "simulation": True}]
    deployment.updated_at = now()
    audit(db, ctx, request, "Rolled back model deployment simulation", "model_deployment", deployment.id)
    db.commit()
    return {"id": deployment.id, "state": deployment.state, "notice": "Rollback is a simulated control-plane state change; no binary was altered."}


@app.get("/api/v1/report-schedules")
def report_schedules_phase3(ctx: Context = Depends(get_context), db: Session = Depends(get_session)) -> list[dict[str, Any]]:
    rows = db.scalars(select(ReportSchedule).where(ReportSchedule.organization_id == ctx.organization_id).order_by(desc(ReportSchedule.created_at))).all()
    return [{"id": x.id, "name": x.name, "project_id": x.project_id, "template": x.template, "frequency": x.frequency, "enabled": x.enabled, "last_run_at": x.last_run_at.isoformat() if x.last_run_at else None} for x in rows]


@app.post("/api/v1/report-schedules")
def create_report_schedule_phase3(body: ScheduleRequest, request: Request, ctx: Context = Depends(require("report:write")), db: Session = Depends(get_session)) -> dict[str, Any]:
    if body.project_id:
        org_item(db, Project, body.project_id, ctx)
    existing = db.scalar(select(ReportSchedule).where(ReportSchedule.organization_id == ctx.organization_id, ReportSchedule.name == body.name))
    if existing:
        return {"id": existing.id, "duplicate": True, "name": existing.name}
    schedule = ReportSchedule(id=make_id("schedule"), organization_id=ctx.organization_id, project_id=body.project_id, name=body.name, template=body.template, frequency=body.frequency, scope={"synthetic": True}, enabled=True, last_run_at=None, created_at=now(), updated_at=now())
    db.add(schedule)
    audit(db, ctx, request, "Created report schedule", "report_schedule", schedule.id, frequency=schedule.frequency)
    db.commit()
    return {"id": schedule.id, "name": schedule.name, "frequency": schedule.frequency, "duplicate": False}


@app.post("/api/v1/report-schedules/{schedule_id}/run-now")
def run_report_schedule_phase3(schedule_id: str, request: Request, ctx: Context = Depends(require("report:write")), db: Session = Depends(get_session)) -> dict[str, Any]:
    schedule = org_item(db, ReportSchedule, schedule_id, ctx)
    project_id = schedule.project_id or db.scalar(select(Project.id).where(Project.organization_id == ctx.organization_id).limit(1))
    if not project_id:
        raise HTTPException(status_code=422, detail="A project is required for scheduled report generation.")
    report = Report(id=make_id("report"), organization_id=ctx.organization_id, project_id=project_id, title=f"{schedule.name} — scheduled run", state="Generated", template=schedule.template, scope={"schedule_id": schedule.id, "synthetic": True}, export_key=None, created_at=now(), updated_at=now())
    db.add(report)
    schedule.last_run_at = now()
    schedule.updated_at = now()
    audit(db, ctx, request, "Ran report schedule", "report_schedule", schedule.id, report_id=report.id)
    db.commit()
    return {"schedule_id": schedule.id, "report_id": report.id, "state": report.state, "notification": "Local console delivery mock recorded."}


@app.get("/api/v1/governance/api-keys")
def list_api_keys_phase3(ctx: Context = Depends(require("model:write")), db: Session = Depends(get_session)) -> list[dict[str, Any]]:
    rows = db.scalars(select(APIKey).where(APIKey.organization_id == ctx.organization_id).order_by(desc(APIKey.created_at))).all()
    return [{"id": x.id, "name": x.name, "prefix": x.key_prefix, "scopes": x.scopes, "expires_at": x.expires_at.isoformat(), "revoked_at": x.revoked_at.isoformat() if x.revoked_at else None} for x in rows]


@app.post("/api/v1/governance/api-keys/{key_id}/revoke")
def revoke_api_key_phase3(key_id: str, request: Request, ctx: Context = Depends(require("model:write")), db: Session = Depends(get_session)) -> dict[str, Any]:
    key = org_item(db, APIKey, key_id, ctx)
    key.revoked_at = now()
    key.updated_at = now()
    audit(db, ctx, request, "Revoked API key", "api_key", key.id)
    db.commit()
    return {"id": key.id, "revoked_at": key.revoked_at.isoformat()}


@app.post("/api/v1/governance/deletion-requests")
def create_deletion_request_phase3(body: DeletionRequestBody, request: Request, ctx: Context = Depends(require("model:write")), db: Session = Depends(get_session)) -> dict[str, Any]:
    existing = db.scalar(select(DeletionRequest).where(DeletionRequest.organization_id == ctx.organization_id, DeletionRequest.request_key == body.request_key))
    if existing:
        return {"id": existing.id, "state": existing.state, "duplicate": True}
    row = DeletionRequest(id=make_id("delete"), organization_id=ctx.organization_id, request_key=body.request_key, scope=body.scope, reason=body.reason, state="Requested", requested_by=ctx.user_id, created_at=now(), updated_at=now())
    db.add(row)
    audit(db, ctx, request, "Created data deletion request", "deletion_request", row.id, scope=body.scope)
    db.commit()
    return {"id": row.id, "state": row.state, "duplicate": False, "notice": "Request is recorded; no evidence is deleted automatically."}


@app.get("/api/v1/search")
def global_search_phase3(q: str = "", limit: int = 8, ctx: Context = Depends(get_context), db: Session = Depends(get_session)) -> dict[str, Any]:
    query = q.strip().lower()
    if not query:
        return {"query": q, "results": []}
    cap = min(max(limit, 1), 25)
    candidates: list[dict[str, Any]] = []
    for label, model, fields, route in [
        ("Asset", Asset, ["name", "asset_type"], "/assets"),
        ("Mission", Mission, ["name", "mission_type"], "/missions"),
        ("Device", Device, ["name", "device_type"], "/devices"),
        ("Work order", WorkOrder, ["title", "status"], "/defects"),
        ("Report", Report, ["title", "template"], "/reports"),
    ]:
        rows = db.scalars(select(model).where(getattr(model, "organization_id") == ctx.organization_id)).all()
        for row in rows:
            haystack = " ".join(str(getattr(row, field, "")) for field in fields).lower()
            if query in haystack or query in str(row.id).lower():
                candidates.append({"id": row.id, "type": label, "name": getattr(row, fields[0]), "status": getattr(row, "state", getattr(row, "status", "Active")), "href": route, "organization_id": ctx.organization_id})
    return {"query": q, "results": candidates[:cap], "notice": "Results are tenant scoped and permission-aware."}


@app.get("/api/v1/media/{media_id}/evidence-package")
def evidence_package_phase3(media_id: str, request: Request, ctx: Context = Depends(get_context), db: Session = Depends(get_session)) -> dict[str, Any]:
    media = org_item(db, MediaFile, media_id, ctx)
    findings = db.scalars(select(Finding).where(Finding.media_id == media.id)).all()
    lineage = media_lineage(media_id, ctx, db)
    audit(db, ctx, request, "Exported synthetic evidence package", "media", media.id)
    db.commit()
    return {"label": "Synthetic demo evidence package — JSON", "media": media_out(media), "findings": [finding_out(x, db) for x in findings], "lineage": lineage, "integrity_notice": "Original media is referenced, never silently modified or merged."}


def api_key_context(
    required_scope: str,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")],
    db: Session,
) -> APIKey:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key is required for developer API access.")
    candidates = db.scalars(select(APIKey).where(APIKey.key_prefix == x_api_key[:12])).all()
    key = next((candidate for candidate in candidates if verify_secret(x_api_key, candidate.secret_hash)), None)
    if not key or key.revoked_at or key.expires_at.replace(tzinfo=timezone.utc) < now():
        raise HTTPException(status_code=401, detail="API key is invalid, expired, or revoked.")
    if required_scope not in key.scopes and "*" not in key.scopes:
        raise HTTPException(status_code=403, detail=f"API key does not include {required_scope} scope.")
    return key


@app.get("/api/v1/developer/projects")
def developer_projects_phase3(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    key = api_key_context("projects:read", x_api_key, db)
    projects = db.scalars(select(Project).where(Project.organization_id == key.organization_id)).all()
    return {"projects": [project_out(project, db) for project in projects], "api_key_prefix": key.key_prefix, "notice": "Scoped developer API response."}
