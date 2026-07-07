"""Small stdlib HTTP client for local integration examples; no third-party SDK dependency."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen


@dataclass
class FieldSightClient:
    base_url: str = "http://localhost:8000"
    token: str | None = None
    workspace: str | None = None

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.workspace:
            headers["X-FieldSight-Workspace"] = self.workspace
        request = Request(f"{self.base_url}{path}", data=json.dumps(payload).encode() if payload is not None else None, headers=headers, method=method)
        with urlopen(request, timeout=20) as response:  # nosec B310 - local example client
            return json.loads(response.read().decode())

    def login(self, email: str, password: str) -> dict[str, Any]:
        result = self._request("POST", "/api/v1/auth/login", {"email": email, "password": password})
        self.token, self.workspace = result["access_token"], result["workspace_id"]
        return result

    def list_missions(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/missions")

    def list_findings(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/findings")

    def list_devices(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/devices")

    def create_work_order(self, finding_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/findings/{finding_id}/work-orders", {"assignee": "Integration demo"})

    def sync_device(self, device_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/devices/{device_id}/sync")

    def create_report(self, title: str = "API Demo Report") -> dict[str, Any]:
        return self._request("POST", "/api/v1/reports", {"title": title})
