from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_and_demo_login():
    assert client.get("/health").json()["status"] == "ok"
    response = client.post(
        "/api/auth/login", json={"email": "admin@fieldsight.demo", "password": "DemoPass123!"}
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "Organization Admin"


def test_review_to_work_order_flow():
    finding = client.get("/api/defects", params={"review_state": "pending"}).json()[0]
    reviewed = client.post(
        f"/api/defects/{finding['id']}/review",
        json={"decision": "approve", "note": "Verified from synthetic evidence."},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["review_state"] == "verified"
    work = client.post(f"/api/defects/{finding['id']}/work-orders", json={"assignee": "Ayesha Malik"})
    assert work.status_code == 200
    assert work.json()["assignee"] == "Ayesha Malik"


def test_edge_sync_and_report_export():
    device = client.post("/api/devices/edge-03/sync")
    assert device.status_code == 200
    report = client.get("/api/reports/export.pdf")
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("application/pdf")
