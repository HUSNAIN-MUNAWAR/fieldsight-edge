from apps.api.app.client import FieldSightClient

client = FieldSightClient()
client.login("admin@fieldsight.demo", "DemoPass123!")
print(client._request("POST", "/api/v1/missions", {"name": "API Mission", "project_id": "prj-solar-alpha", "site_id": "site-alpha-a", "mission_type": "Routine inspection"}))
