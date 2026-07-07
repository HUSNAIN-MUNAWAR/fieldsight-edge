from fastapi.testclient import TestClient
from uuid import uuid4
from app.main import app


def login(client: TestClient, email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "DemoPass123!"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_workspace_and_cross_tenant_asset_blocked():
    with TestClient(app) as client:
        reviewer = login(client, "reviewer@solarvista.demo")
        headers = {"Authorization": f"Bearer {reviewer}"}
        own = client.get("/api/v1/assets/asset-001", headers=headers)
        assert own.status_code == 200
        other = client.get("/api/v1/assets/asset-004", headers=headers)
        assert other.status_code == 404
        denied_workspace = client.get(
            "/api/v1/workspaces", headers={**headers, "X-FieldSight-Workspace": "org-atlas"}
        )
        assert denied_workspace.status_code == 403


def test_media_intake_duplicate_and_deterministic_inference():
    with TestClient(app) as client:
        nonce = uuid4().hex.encode()
        content = b"\xff\xd8" + (b"phase2-demo-image-" + nonce) * 80
        files = {"file": ("phase2-intake.jpg", content, "image/jpeg")}
        data = {"asset_id": "asset-001"}
        first = client.post(
            "/api/v1/media/intake",
            files=files,
            data=data,
            headers={"Idempotency-Key": f"phase2-media-{nonce.decode()}"},
        )
        assert first.status_code == 200
        assert first.json()["finding"]["model_version"]
        duplicate = client.post("/api/v1/media/intake", files=files, data=data)
        assert duplicate.status_code == 200
        assert duplicate.json()["duplicate"] is True


def test_offline_capture_sync_and_risk_change_flow():
    with TestClient(app) as client:
        assert client.post("/api/v1/devices/edge-03/mode", json={"mode": "offline"}).status_code == 200
        capture = client.post("/api/v1/devices/edge-03/capture")
        assert capture.status_code == 200
        assert capture.json()["sync_job"]["state"] == "Queued offline"
        sync = client.post("/api/v1/devices/edge-03/sync")
        assert sync.status_code == 200
        assert sync.json()["synchronized_jobs"] >= 1
        risk = client.get("/api/v1/assets/asset-001/risk")
        assert risk.status_code == 200
        assert 0 <= risk.json()["score"] <= 100
        change = client.get("/api/v1/assets/asset-001/changes")
        assert change.status_code == 200
        assert "finding_delta" in change.json()


def test_critical_review_work_order_approval_and_report():
    with TestClient(app) as client:
        pending = client.get("/api/v1/findings", params={"review_state": "pending"}).json()
        critical = next(item for item in pending if item["severity"] == "critical")
        reviewed = client.post(
            f"/api/v1/findings/{critical['id']}/review",
            json={"decision": "approve", "note": "Phase 2 synthetic verification."},
        )
        assert reviewed.status_code == 200
        work = client.post(
            f"/api/v1/findings/{critical['id']}/work-orders",
            json={"assignee": "Field Ops North", "estimated_cost": 6500},
        )
        assert work.status_code == 200
        assert work.json()["status"] == "Awaiting approval"
        approved = client.post(f"/api/v1/work-orders/{work.json()['id']}/approve")
        assert approved.status_code == 200
        assert approved.json()["status"] == "Approved"
        assert (
            client.get("/api/v1/reports/export.pdf").headers["content-type"].startswith("application/pdf")
        )
