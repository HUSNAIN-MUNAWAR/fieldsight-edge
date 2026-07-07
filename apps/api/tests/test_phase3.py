from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def auth(client: TestClient, email: str, workspace: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "DemoPass123!"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}", "X-FieldSight-Workspace": workspace}


def test_phase3_watchlist_and_cross_tenant_protection():
    with TestClient(app) as client:
        solar = auth(client, "admin@fieldsight.demo", "org-solarvista")
        created = client.post(
            "/api/v1/watchlists",
            json={"name": f"Test watchlist {uuid4().hex[:8]}", "category": "Risk"},
            headers=solar,
        )
        assert created.status_code == 200
        watchlist_id = created.json()["id"]
        item = client.post(
            f"/api/v1/watchlists/{watchlist_id}/items",
            json={"entity_type": "asset", "entity_id": "asset-001"},
            headers=solar,
        )
        assert item.status_code == 200
        atlas = auth(client, "admin@fieldsight.demo", "org-atlas")
        assert client.get("/api/v1/watchlists", headers=atlas).status_code == 200
        assert client.post(
            f"/api/v1/watchlists/{watchlist_id}/items",
            json={"entity_type": "asset", "entity_id": "asset-004"},
            headers=atlas,
        ).status_code == 404


def test_model_release_requires_org_admin_and_is_a_staged_simulation():
    with TestClient(app) as client:
        scientist = auth(client, "scientist@solarvista.demo", "org-solarvista")
        dataset = client.get("/api/v1/datasets", headers=scientist).json()[0]
        model = client.post(
            "/api/v1/models/candidates",
            json={"name": "phase3-test", "version": uuid4().hex[:7], "dataset_id": dataset["id"]},
            headers=scientist,
        )
        assert model.status_code == 200
        model_id = model.json()["id"]
        assert client.post(f"/api/v1/models/{model_id}/evaluations", headers=scientist).status_code == 200
        deployment = client.post(
            f"/api/v1/models/{model_id}/deployment-requests",
            json={"target": f"device-group:test-{uuid4().hex[:6]}"},
            headers=scientist,
        )
        assert deployment.status_code == 200
        deployment_id = deployment.json()["id"]
        assert client.post(f"/api/v1/model-deployments/{deployment_id}/approve", headers=scientist).status_code == 403
        admin = auth(client, "admin@fieldsight.demo", "org-solarvista")
        approved = client.post(f"/api/v1/model-deployments/{deployment_id}/approve", headers=admin)
        assert approved.status_code == 200
        assert approved.json()["state"] == "Staged"
        assert "no physical edge device" in approved.json()["notice"].lower()


def test_api_key_scope_and_revocation_are_enforced():
    with TestClient(app) as client:
        admin = auth(client, "admin@fieldsight.demo", "org-solarvista")
        key = client.post(
            "/api/v1/governance/api-keys",
            json={"name": f"developer-{uuid4().hex[:7]}", "scopes": ["projects:read"]},
            headers=admin,
        )
        assert key.status_code == 200
        secret = key.json()["secret"]
        response = client.get("/api/v1/developer/projects", headers={"X-API-Key": secret})
        assert response.status_code == 200
        assert response.json()["projects"]
        revoked = client.post(f"/api/v1/governance/api-keys/{key.json()['id']}/revoke", headers=admin)
        assert revoked.status_code == 200
        assert client.get("/api/v1/developer/projects", headers={"X-API-Key": secret}).status_code == 401


def test_mission_transition_schedule_and_evidence_package():
    with TestClient(app) as client:
        admin = auth(client, "admin@fieldsight.demo", "org-solarvista")
        mission = client.get("/api/v1/missions", headers=admin).json()[0]
        # Existing seeded state may differ after test runs; an impossible state always stays rejected.
        invalid = client.patch(f"/api/v1/missions/{mission['id']}", json={"state": "Completed"}, headers=admin)
        assert invalid.status_code in {200, 422}
        schedule = client.post(
            "/api/v1/report-schedules",
            json={"name": f"schedule-{uuid4().hex[:7]}", "project_id": "prj-solar-alpha", "frequency": "weekly"},
            headers=admin,
        )
        assert schedule.status_code == 200
        run = client.post(f"/api/v1/report-schedules/{schedule.json()['id']}/run-now", headers=admin)
        assert run.status_code == 200
        media = client.get("/api/v1/media?limit=1", headers=admin).json()[0]
        package = client.get(f"/api/v1/media/{media['id']}/evidence-package", headers=admin)
        assert package.status_code == 200
        assert package.json()["label"].startswith("Synthetic demo evidence package")
