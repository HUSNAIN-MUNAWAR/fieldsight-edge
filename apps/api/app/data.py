from __future__ import annotations

from datetime import datetime, timedelta, timezone
from random import Random
from typing import Any

rng = Random(42)
NOW = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)

TAXONOMY = {
    "damaged_panel": {"label": "Damaged panel", "severity": "critical", "color": "#ff7a00"},
    "soiling": {"label": "Soiling", "severity": "medium", "color": "#e6bb35"},
    "vegetation_obstruction": {"label": "Vegetation obstruction", "severity": "high", "color": "#ca9d2c"},
    "hotspot_risk": {"label": "Hotspot-risk marker", "severity": "high", "color": "#fb9530"},
    "frame_corrosion": {"label": "Frame corrosion", "severity": "medium", "color": "#b38c72"},
    "missing_panel": {"label": "Missing panel", "severity": "critical", "color": "#e35537"},
    "inverter_issue": {"label": "Inverter cabinet issue", "severity": "high", "color": "#f06d32"},
}

PROJECTS = [
    {
        "id": "prj-solar-alpha",
        "name": "Solar Farm Alpha",
        "industry": "Solar",
        "site_count": 2,
        "coverage": 94,
        "status": "Active",
        "last_inspection": "2026-07-06",
    },
    {
        "id": "prj-utility-north",
        "name": "North Utility Corridor",
        "industry": "Utilities",
        "site_count": 3,
        "coverage": 72,
        "status": "Active",
        "last_inspection": "2026-07-03",
    },
    {
        "id": "prj-roof-east",
        "name": "East Campus Roofing",
        "industry": "Facilities",
        "site_count": 1,
        "coverage": 58,
        "status": "Planning",
        "last_inspection": "2026-06-26",
    },
]

SITES = [
    {
        "id": "site-alpha-a",
        "project_id": "prj-solar-alpha",
        "name": "Alpha East Array",
        "lat": 33.618,
        "lng": 73.063,
        "risk": 74,
        "coverage": 96,
        "zone": "Zone C",
    },
    {
        "id": "site-alpha-b",
        "project_id": "prj-solar-alpha",
        "name": "Alpha Inverter Yard",
        "lat": 33.622,
        "lng": 73.071,
        "risk": 52,
        "coverage": 91,
        "zone": "Zone A",
    },
    {
        "id": "site-utility-a",
        "project_id": "prj-utility-north",
        "name": "North Corridor 01",
        "lat": 33.657,
        "lng": 73.051,
        "risk": 39,
        "coverage": 76,
        "zone": "Segment 1",
    },
    {
        "id": "site-utility-b",
        "project_id": "prj-utility-north",
        "name": "North Corridor 02",
        "lat": 33.671,
        "lng": 73.044,
        "risk": 61,
        "coverage": 67,
        "zone": "Segment 2",
    },
    {
        "id": "site-utility-c",
        "project_id": "prj-utility-north",
        "name": "North Corridor 03",
        "lat": 33.682,
        "lng": 73.035,
        "risk": 48,
        "coverage": 73,
        "zone": "Segment 3",
    },
    {
        "id": "site-roof-a",
        "project_id": "prj-roof-east",
        "name": "East Campus Roof",
        "lat": 33.602,
        "lng": 73.094,
        "risk": 28,
        "coverage": 58,
        "zone": "Roof A",
    },
]

ASSET_TYPES = ["PV module row", "Inverter cabinet", "Combiner box", "Service road", "Perimeter fence"]
ASSETS: list[dict[str, Any]] = []
for i in range(250):
    site = SITES[i % len(SITES)]
    asset_type = ASSET_TYPES[i % len(ASSET_TYPES)]
    ASSETS.append(
        {
            "id": f"asset-{i + 1:03d}",
            "site_id": site["id"],
            "name": f"{('PV-' if asset_type == 'PV module row' else 'AS-')}{i + 1:03d}",
            "asset_type": asset_type,
            "lat": round(site["lat"] + rng.uniform(-0.006, 0.006), 6),
            "lng": round(site["lng"] + rng.uniform(-0.008, 0.008), 6),
            "risk_score": rng.randint(12, 88),
            "last_inspected": (NOW - timedelta(days=rng.randint(0, 89))).date().isoformat(),
            "status": "Needs review" if i % 7 == 0 else "Monitored",
        }
    )

MEDIA: list[dict[str, Any]] = []
for i in range(400):
    asset = ASSETS[i % len(ASSETS)]
    MEDIA.append(
        {
            "id": f"img-{i + 1:03d}",
            "asset_id": asset["id"],
            "site_id": asset["site_id"],
            "filename": f"capture_{i + 1:04d}.jpg",
            "captured_at": (NOW - timedelta(days=i % 90, hours=i % 12)).isoformat(),
            "source": ["Drone · Mavic 3E", "Mobile · FieldSight Capture", "Edge · FS-CAM-02"][i % 3],
            "lat": asset["lat"],
            "lng": asset["lng"],
            "width": 1920,
            "height": 1080,
            "checksum": f"sha256:demo{i:04x}{(i * 13):04x}",
        }
    )

DETECTIONS: list[dict[str, Any]] = []
classes = list(TAXONOMY)
for i in range(155):
    media = MEDIA[i % len(MEDIA)]
    class_key = classes[i % len(classes)]
    tax = TAXONOMY[class_key]
    confidence = round(0.52 + ((i * 37) % 45) / 100, 2)
    review_state = "verified" if i < 83 else ("pending" if confidence < 0.78 else "auto-accepted")
    DETECTIONS.append(
        {
            "id": f"det-{i + 1:03d}",
            "media_id": media["id"],
            "asset_id": media["asset_id"],
            "class_key": class_key,
            "label": tax["label"],
            "severity": tax["severity"],
            "confidence": confidence,
            "review_state": review_state,
            "model_version": "vision-solar-1.4.2" if i % 3 else "vision-solar-1.5.0-rc1",
            "bbox": {
                "x": 14 + (i * 7) % 54,
                "y": 12 + (i * 11) % 46,
                "w": 18 + (i % 15),
                "h": 14 + ((i * 3) % 16),
            },
            "mask": [[20, 20], [42, 16], [55, 35], [45, 51], [22, 44]],
            "created_at": media["captured_at"],
            "review_note": "",
            "reviewed_by": None,
        }
    )

WORK_ORDERS: list[dict[str, Any]] = []
for i in range(32):
    d = DETECTIONS[i]
    WORK_ORDERS.append(
        {
            "id": f"wo-{i + 1:03d}",
            "title": f"Remediate {d['label'].lower()} — {d['asset_id'].upper()}",
            "detection_id": d["id"],
            "asset_id": d["asset_id"],
            "severity": d["severity"],
            "status": ["Assigned", "In progress", "Resolved", "New"][i % 4],
            "assignee": ["Ayesha Malik", "Bilal Ahmed", "Field Ops North", "Unassigned"][i % 4],
            "sla_due": (NOW + timedelta(days=(i % 8) + 1)).date().isoformat(),
            "created_at": (NOW - timedelta(days=i % 30)).isoformat(),
        }
    )

DEVICES = [
    {
        "id": "edge-01",
        "name": "FS-DRONE-ALPHA",
        "site": "Alpha East Array",
        "state": "online",
        "battery": 86,
        "cpu": 42,
        "temp": 54,
        "storage": 61,
        "last_sync": "2m ago",
        "model": "vision-solar-1.4.2",
        "pending": 0,
    },
    {
        "id": "edge-02",
        "name": "FS-CAM-02",
        "site": "Alpha Inverter Yard",
        "state": "syncing",
        "battery": 74,
        "cpu": 58,
        "temp": 61,
        "storage": 72,
        "last_sync": "syncing now",
        "model": "vision-solar-1.4.2",
        "pending": 18,
    },
    {
        "id": "edge-03",
        "name": "FS-DRONE-NORTH",
        "site": "North Corridor 02",
        "state": "offline",
        "battery": 31,
        "cpu": 0,
        "temp": 32,
        "storage": 83,
        "last_sync": "46m ago",
        "model": "vision-solar-1.3.8",
        "pending": 26,
    },
    {
        "id": "edge-04",
        "name": "FS-ROOF-EAST",
        "site": "East Campus Roof",
        "state": "online",
        "battery": 100,
        "cpu": 19,
        "temp": 42,
        "storage": 39,
        "last_sync": "6m ago",
        "model": "vision-solar-1.4.2",
        "pending": 0,
    },
    {
        "id": "edge-05",
        "name": "FS-UTILITY-01",
        "site": "North Corridor 01",
        "state": "online",
        "battery": 67,
        "cpu": 37,
        "temp": 49,
        "storage": 46,
        "last_sync": "12m ago",
        "model": "vision-solar-1.4.2",
        "pending": 3,
    },
]

MODELS = [
    {
        "id": "model-1.3.8",
        "version": "vision-solar-1.3.8",
        "status": "retired",
        "precision": 0.84,
        "recall": 0.79,
        "acceptance": 0.71,
        "drift": 0.18,
        "deployed_to": 1,
    },
    {
        "id": "model-1.4.2",
        "version": "vision-solar-1.4.2",
        "status": "production",
        "precision": 0.91,
        "recall": 0.88,
        "acceptance": 0.86,
        "drift": 0.07,
        "deployed_to": 4,
    },
    {
        "id": "model-1.5.0",
        "version": "vision-solar-1.5.0-rc1",
        "status": "validation",
        "precision": 0.94,
        "recall": 0.89,
        "acceptance": 0.0,
        "drift": 0.04,
        "deployed_to": 0,
    },
]

AUDIT_EVENTS = [
    {
        "id": "audit-1",
        "at": "2026-07-07T09:42:00+00:00",
        "actor": "Ayesha Malik",
        "action": "Verified a high-severity vegetation obstruction",
        "target": "DET-011",
        "metadata": "Severity held at high",
    },
    {
        "id": "audit-2",
        "at": "2026-07-07T09:28:00+00:00",
        "actor": "FS-CAM-02",
        "action": "Queued 18 captures while offline",
        "target": "EDGE-02",
        "metadata": "Connectivity intermittent",
    },
    {
        "id": "audit-3",
        "at": "2026-07-07T08:54:00+00:00",
        "actor": "System",
        "action": "Created critical alert",
        "target": "PV-015",
        "metadata": "Damaged panel confidence 0.93",
    },
]


def index(items: list[dict[str, Any]], item_id: str) -> dict[str, Any] | None:
    return next((x for x in items if x["id"] == item_id), None)


def asset_for(asset_id: str) -> dict[str, Any] | None:
    return index(ASSETS, asset_id)


def media_for(media_id: str) -> dict[str, Any] | None:
    return index(MEDIA, media_id)


def detection_for(detection_id: str) -> dict[str, Any] | None:
    return index(DETECTIONS, detection_id)


def project_summary() -> dict[str, Any]:
    critical = sum(1 for d in DETECTIONS if d["severity"] == "critical" and d["review_state"] != "rejected")
    return {
        "kpis": {
            "active_projects": 3,
            "new_findings": 47,
            "critical_defects": critical,
            "pending_review": sum(1 for d in DETECTIONS if d["review_state"] == "pending"),
            "open_work_orders": sum(1 for x in WORK_ORDERS if x["status"] != "Resolved"),
            "sync_queue": sum(x["pending"] for x in DEVICES),
        },
        "priority": sorted(
            [d for d in DETECTIONS if d["severity"] in {"critical", "high"}],
            key=lambda d: (d["severity"] != "critical", -d["confidence"]),
        )[:7],
        "coverage": [{"day": f"Jul {i + 1}", "coverage": 48 + (i * 7) % 45} for i in range(7)],
        "insight": "Since the previous Alpha flight, 6 new potential issues were found. Two require immediate review before the afternoon maintenance window.",
    }
