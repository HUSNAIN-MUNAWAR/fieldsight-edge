from apps.api.app.client import FieldSightClient

client = FieldSightClient()
client.login("reviewer@solarvista.demo", "DemoPass123!")
findings = client.list_findings()
pending = next(item for item in findings if item["review_state"] == "pending")
print(client._request("POST", f"/api/v1/findings/{pending['id']}/review", {"decision": "approve", "note": "Reviewed through API example."}))
