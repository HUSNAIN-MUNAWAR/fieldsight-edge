from __future__ import annotations

from datetime import datetime, timedelta, timezone
from random import Random

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Alert,
    Asset,
    AssetRiskSnapshot,
    AuditEvent,
    DatasetVersion,
    Device,
    Finding,
    MediaFile,
    Membership,
    Mission,
    ModelVersion,
    Organization,
    Project,
    Report,
    Site,
    SyncJob,
    User,
    WorkOrder,
)
from .security import hash_secret
from .services.inference import TAXONOMY

NOW = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)
RNG = Random(42)


def stamp(model: object) -> object:
    setattr(model, "created_at", NOW)
    setattr(model, "updated_at", NOW)
    return model


def ensure(db: Session, model: type, identity: str, **values: object) -> object:
    existing = db.get(model, identity)
    if existing:
        return existing
    return stamp(model(id=identity, **values))


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(Organization.id).limit(1)):
        return
    org_specs = [
        ("org-solarvista", "SolarVista Operations", "solarvista", "Renewable energy"),
        ("org-atlas", "Atlas Infrastructure Services", "atlas", "Infrastructure inspection"),
        ("org-meridian", "Meridian Facilities Group", "meridian", "Facilities management"),
    ]
    for oid, name, slug, industry in org_specs:
        db.add(
            ensure(
                db,
                Organization,
                oid,
                name=name,
                slug=slug,
                industry=industry,
                settings={"retention_days": 365, "demo": True},
            )
        )
    users = [
        ("usr-platform", "admin@fieldsight.demo", "Husnain Demo", True),
        ("usr-reviewer-solar", "reviewer@solarvista.demo", "Ayesha Malik", False),
        ("usr-operator-atlas", "operator@atlas.demo", "Bilal Ahmed", False),
        ("usr-maint-meridian", "maintenance@meridian.demo", "Nadia Khan", False),
    ]
    for uid, email, name, platform in users:
        db.add(
            ensure(
                db,
                User,
                uid,
                email=email,
                name=name,
                password_hash=hash_secret("DemoPass123!"),
                is_platform_admin=platform,
                active=True,
            )
        )
    memberships = [
        ("mem-platform-solar", "usr-platform", "org-solarvista", "Organization Admin"),
        ("mem-platform-atlas", "usr-platform", "org-atlas", "Organization Admin"),
        ("mem-platform-meridian", "usr-platform", "org-meridian", "Organization Admin"),
        ("mem-reviewer-solar", "usr-reviewer-solar", "org-solarvista", "Reviewer"),
        ("mem-operator-atlas", "usr-operator-atlas", "org-atlas", "Field Operator"),
        ("mem-maint-meridian", "usr-maint-meridian", "org-meridian", "Maintenance Coordinator"),
    ]
    for mid, uid, oid, role in memberships:
        db.add(
            ensure(db, Membership, mid, user_id=uid, organization_id=oid, role=role, site_restrictions=[])
        )
    project_specs = [
        ("prj-solar-alpha", "org-solarvista", "Solar Farm Alpha", "Solar", "Active"),
        ("prj-utility-north", "org-atlas", "North Utility Corridor", "Utilities", "Active"),
        ("prj-roof-east", "org-meridian", "East Campus Roofing", "Facilities", "Planning"),
    ]
    for pid, oid, name, industry, status in project_specs:
        db.add(
            ensure(
                db,
                Project,
                pid,
                organization_id=oid,
                name=name,
                industry=industry,
                status=status,
                metadata_json={"demo": True},
            )
        )
    site_specs = [
        ("site-alpha-a", "org-solarvista", "prj-solar-alpha", "Alpha East Array", 33.618, 73.063, 96, 74),
        (
            "site-alpha-b",
            "org-solarvista",
            "prj-solar-alpha",
            "Alpha Inverter Yard",
            33.622,
            73.071,
            91,
            52,
        ),
        ("site-utility-a", "org-atlas", "prj-utility-north", "North Corridor 01", 33.657, 73.051, 76, 39),
        ("site-utility-b", "org-atlas", "prj-utility-north", "North Corridor 02", 33.671, 73.044, 67, 61),
        ("site-utility-c", "org-atlas", "prj-utility-north", "North Corridor 03", 33.682, 73.035, 73, 48),
        ("site-roof-a", "org-meridian", "prj-roof-east", "East Campus Roof", 33.602, 73.094, 58, 28),
    ]
    for sid, oid, pid, name, lat, lng, coverage, risk in site_specs:
        boundary = {
            "type": "Polygon",
            "coordinates": [
                [
                    [lng - 0.004, lat - 0.003],
                    [lng + 0.004, lat - 0.003],
                    [lng + 0.004, lat + 0.003],
                    [lng - 0.004, lat + 0.003],
                    [lng - 0.004, lat - 0.003],
                ]
            ],
        }
        db.add(
            ensure(
                db,
                Site,
                sid,
                organization_id=oid,
                project_id=pid,
                name=name,
                latitude=lat,
                longitude=lng,
                boundary=boundary,
                coverage_percent=coverage,
                risk_score=risk,
            )
        )
    db.flush()
    sites = db.scalars(select(Site).order_by(Site.id)).all()
    asset_types = ["PV module row", "Inverter cabinet", "Combiner box", "Service road", "Perimeter fence"]
    assets: list[Asset] = []
    for i in range(250):
        site = sites[i % len(sites)]
        atype = asset_types[i % len(asset_types)]
        asset = ensure(
            db,
            Asset,
            f"asset-{i + 1:03d}",
            organization_id=site.organization_id,
            site_id=site.id,
            name=f"{'PV-' if atype == 'PV module row' else 'AS-'}{i + 1:03d}",
            asset_type=atype,
            latitude=round(site.latitude + RNG.uniform(-0.006, 0.006), 6),
            longitude=round(site.longitude + RNG.uniform(-0.008, 0.008), 6),
            criticality="critical" if i % 17 == 0 else "standard",
            tags=["demo", atype.lower().replace(" ", "-")],
            metadata_json={"installed_year": 2023},
        )
        db.add(asset)
        assets.append(asset)
    db.flush()
    model_specs = [
        ("model-1.3.8", "vision-solar-1.3.8", "Deprecated", 0.84, 0.79, 0.18),
        ("model-1.4.2", "vision-solar-1.4.2", "Deployed", 0.91, 0.88, 0.07),
        ("model-1.5.0", "vision-solar-1.5.0-rc1", "Validating", 0.94, 0.89, 0.04),
    ]
    for mid, version, state, precision, recall, drift in model_specs:
        db.add(
            ensure(
                db,
                ModelVersion,
                mid,
                organization_id=None,
                name="SolarVision",
                version=version,
                state=state,
                model_family="YOLO-compatible adapter",
                task_type="detection and segmentation",
                runtime="deterministic-demo",
                metrics={
                    "precision_proxy": precision,
                    "recall_proxy": recall,
                    "f1_proxy": round(2 * precision * recall / (precision + recall), 2),
                    "drift": drift,
                    "synthetic": True,
                },
                model_card={
                    "limitations": "Seeded synthetic metrics. Not real-world accuracy.",
                    "classes": list(TAXONOMY),
                },
            )
        )
    db.flush()
    media: list[MediaFile] = []
    for i in range(400):
        asset = assets[i % len(assets)]
        media_item = ensure(
            db,
            MediaFile,
            f"img-{i + 1:03d}",
            organization_id=asset.organization_id,
            asset_id=asset.id,
            site_id=asset.site_id,
            mission_id=None,
            device_id=None,
            filename=f"capture_{i + 1:04d}.jpg",
            content_type="image/jpeg",
            storage_key=f"synthetic/{asset.organization_id}/capture_{i + 1:04d}.jpg",
            checksum=f"sha256:demo{i:04x}{(i * 13):04x}",
            byte_size=2048 + i,
            captured_at=NOW - timedelta(days=i % 90, hours=i % 12),
            latitude=asset.latitude,
            longitude=asset.longitude,
            width=1920,
            height=1080,
            source=["Drone · Mavic 3E", "Mobile · FieldSight Capture", "Edge · FS-CAM-02"][i % 3],
            validation={"state": "Healthy", "gps": True, "timestamp": True, "synthetic": True},
            quality={"score": 86 + i % 12, "warnings": []},
        )
        db.add(media_item)
        media.append(media_item)
    db.flush()
    classes = list(TAXONOMY)
    findings: list[Finding] = []
    for i in range(155):
        item = media[i]
        c = classes[i % len(classes)]
        tax = TAXONOMY[c]
        confidence = round(0.52 + ((i * 37) % 45) / 100, 2)
        state = "verified" if i < 83 else ("pending" if confidence < 0.78 else "auto-accepted")
        f = ensure(
            db,
            Finding,
            f"det-{i + 1:03d}",
            organization_id=item.organization_id,
            media_id=item.id,
            asset_id=item.asset_id,
            inference_job_id=None,
            defect_class=c,
            defect_subclass=None,
            severity=tax["severity"],
            confidence=confidence,
            review_state=state,
            bbox={
                "x": 14 + (i * 7) % 54,
                "y": 12 + (i * 11) % 46,
                "w": 18 + i % 15,
                "h": 14 + (i * 3) % 16,
            },
            mask=[[20, 20], [42, 16], [55, 35], [45, 51], [22, 44]],
            quality_warnings=[],
            reviewed_by="usr-reviewer-solar"
            if state == "verified" and item.organization_id == "org-solarvista"
            else None,
            reviewer_decision="approve" if state == "verified" else None,
            reviewer_note="Seeded verification" if state == "verified" else None,
            training_candidate=i % 11 == 0,
            human_override={},
        )
        db.add(f)
        findings.append(f)
    db.flush()
    for i in range(32):
        f = findings[i]
        asset = next(a for a in assets if a.id == f.asset_id)
        status = ["Approved", "In progress", "Completed", "Draft"][i % 4]
        wo = ensure(
            db,
            WorkOrder,
            f"wo-{i + 1:03d}",
            organization_id=f.organization_id,
            asset_id=f.asset_id,
            finding_id=f.id,
            defect_id=None,
            mission_id=None,
            title=f"Remediate {f.defect_class.replace('_', ' ')} — {asset.name}",
            description="Synthetic evidence-led maintenance work order.",
            severity=f.severity,
            priority=f.severity,
            status=status,
            assignee=["Ayesha Malik", "Bilal Ahmed", "Field Ops North", "Unassigned"][i % 4],
            due_date=(NOW + timedelta(days=(i % 8) + 1)).date().isoformat(),
            estimated_cost=1500 + (i % 5) * 550,
            checklist=[
                {"task": "Confirm lock-out procedure", "done": status in {"Completed"}},
                {"task": "Attach resolution evidence", "done": status in {"Completed"}},
            ],
            resolution_evidence=[]
            if status != "Completed"
            else [{"type": "synthetic-image", "note": "Resolution evidence placeholder"}],
            approval_history=[],
        )
        db.add(wo)
    device_specs = [
        (
            "edge-01",
            "org-solarvista",
            "site-alpha-a",
            "FS-DRONE-ALPHA",
            "Drone companion",
            "online",
            86,
            42,
            61,
            0,
        ),
        (
            "edge-02",
            "org-solarvista",
            "site-alpha-b",
            "FS-CAM-02",
            "Fixed camera",
            "syncing",
            74,
            58,
            72,
            18,
        ),
        (
            "edge-03",
            "org-solarvista",
            "site-alpha-a",
            "FS-DRONE-NORTH",
            "Drone companion",
            "offline",
            31,
            0,
            83,
            26,
        ),
        (
            "edge-04",
            "org-meridian",
            "site-roof-a",
            "FS-ROOF-EAST",
            "Mobile gateway",
            "online",
            100,
            19,
            39,
            0,
        ),
        (
            "edge-05",
            "org-atlas",
            "site-utility-a",
            "FS-UTILITY-01",
            "Fixed camera",
            "online",
            67,
            37,
            46,
            3,
        ),
    ]
    for did, oid, sid, name, dtype, state, battery, cpu, storage, queue in device_specs:
        db.add(
            ensure(
                db,
                Device,
                did,
                organization_id=oid,
                site_id=sid,
                name=name,
                device_type=dtype,
                state=state,
                model_version="vision-solar-1.4.2",
                health={
                    "battery": battery,
                    "cpu": cpu,
                    "temperature": 32 + cpu // 2,
                    "storage": storage,
                    "network_quality": "degraded" if state == "offline" else "healthy",
                    "queue_count": queue,
                    "failed_sync": 1 if did == "edge-03" else 0,
                },
                config={"offline_enabled": True, "model_profile": "default"},
                last_seen_at=NOW - timedelta(minutes=46 if state == "offline" else 2),
            )
        )
    db.flush()
    for i in range(5):
        device = db.get(Device, f"edge-0{i + 1}")
        if device:
            db.add(
                ensure(
                    db,
                    SyncJob,
                    f"sync-seed-{i + 1}",
                    organization_id=device.organization_id,
                    device_id=device.id,
                    media_id=None,
                    state="Queued offline" if device.state == "offline" else "Synchronized",
                    retry_count=1 if device.state == "offline" else 0,
                    idempotency_key=f"seed-sync-{i + 1}",
                    error="synthetic connectivity interruption" if device.state == "offline" else None,
                )
            )
    mission_specs = [
        (
            "mission-alpha-1",
            "org-solarvista",
            "prj-solar-alpha",
            "site-alpha-a",
            "Alpha Zone C follow-up",
            "Follow-up inspection",
            "Under review",
            "high",
            "Ayesha Malik",
            "edge-01",
        ),
        (
            "mission-atlas-1",
            "org-atlas",
            "prj-utility-north",
            "site-utility-b",
            "Corridor 02 routine sweep",
            "Routine inspection",
            "Assigned",
            "normal",
            "Bilal Ahmed",
            "edge-03",
        ),
        (
            "mission-meridian-1",
            "org-meridian",
            "prj-roof-east",
            "site-roof-a",
            "Roof seasonal verification",
            "Maintenance verification",
            "Planned",
            "high",
            "Nadia Khan",
            "edge-04",
        ),
    ]
    for mid, oid, pid, sid, name, typ, state, priority, operator, device in mission_specs:
        db.add(
            ensure(
                db,
                Mission,
                mid,
                organization_id=oid,
                project_id=pid,
                site_id=sid,
                name=name,
                mission_type=typ,
                state=state,
                priority=priority,
                assigned_operator=operator,
                assigned_device_id=device,
                due_date="2026-07-10",
                zones=["Zone C"],
                checklist=[
                    {"label": "Flight safety brief", "done": True},
                    {"label": "Minimum resolution check", "done": False},
                ],
                settings={
                    "offline_enabled": True,
                    "model_profile": "solar-default",
                    "review_policy": "critical-human-confirmation",
                },
            )
        )
    for aid, oid, category, severity, entity_type, entity_id, title in [
        (
            "alert-1",
            "org-solarvista",
            "critical_defect",
            "critical",
            "finding",
            "det-001",
            "Critical panel damage awaiting work-order approval",
        ),
        (
            "alert-2",
            "org-atlas",
            "device_offline",
            "high",
            "device",
            "edge-03",
            "FS-DRONE-NORTH offline with 26 queued captures",
        ),
        (
            "alert-3",
            "org-meridian",
            "coverage_gap",
            "medium",
            "site",
            "site-roof-a",
            "Roof coverage below planned threshold",
        ),
    ]:
        db.add(
            ensure(
                db,
                Alert,
                aid,
                organization_id=oid,
                category=category,
                severity=severity,
                state="Open",
                title=title,
                entity_type=entity_type,
                entity_id=entity_id,
                detail={"synthetic": True, "suggested_action": "Review and assign an operator"},
            )
        )
    for oid, pid, title in [
        ("org-solarvista", "prj-solar-alpha", "Solar Farm Alpha — Inspection Report"),
        ("org-atlas", "prj-utility-north", "North Utility Corridor — Weekly Summary"),
        ("org-meridian", "prj-roof-east", "East Campus Roof — Coverage Review"),
    ]:
        db.add(
            ensure(
                db,
                Report,
                f"report-{oid}",
                organization_id=oid,
                project_id=pid,
                title=title,
                state="Generated",
                template="executive",
                scope={"synthetic": True},
                export_key=None,
            )
        )
        db.add(
            ensure(
                db,
                DatasetVersion,
                f"dataset-{oid}",
                organization_id=oid,
                name="inspection-feedback-v1",
                source="review-corrections",
                image_count=120,
                annotation_count=176,
                summary={
                    "synthetic": True,
                    "reviewer_coverage": 0.84,
                    "known_issues": ["Synthetic demo metrics"],
                },
            )
        )
    for i, asset in enumerate(assets[:80]):
        related = [f for f in findings if f.asset_id == asset.id and f.review_state != "rejected"]
        if related:
            severity = related[0].severity
            score = min(100, 22 + {"critical": 62, "high": 42, "medium": 26}.get(severity, 12))
            level = "Critical" if score > 80 else "High" if score > 60 else "Moderate"
            db.add(
                ensure(
                    db,
                    AssetRiskSnapshot,
                    f"risk-{asset.id}",
                    organization_id=asset.organization_id,
                    asset_id=asset.id,
                    score=score,
                    level=level,
                    drivers=[
                        {
                            "driver": "Seeded demo risk estimate",
                            "impact": score - 22,
                            "detail": "Evidence and maintenance state contribute",
                        }
                    ],
                    overridden_by=None,
                )
            )
    for i, event in enumerate(
        [
            (
                "org-solarvista",
                "Ayesha Malik",
                "Verified synthetic high-severity vegetation obstruction",
                "finding",
                "det-011",
            ),
            ("org-atlas", "FS-DRONE-NORTH", "Queued captures while offline", "device", "edge-03"),
            ("org-solarvista", "System", "Created critical finding alert", "asset", "asset-001"),
        ],
        1,
    ):
        oid, actor, action, ttype, tid = event
        db.add(
            AuditEvent(
                id=f"audit-{i}",
                organization_id=oid,
                occurred_at=NOW - timedelta(minutes=i * 14),
                actor_id=None,
                actor_name=actor,
                action=action,
                target_type=ttype,
                target_id=tid,
                request_id="seed",
                metadata_json={"synthetic": True},
            )
        )
    db.commit()
