from apps.api.app.client import FieldSightClient

client = FieldSightClient()
client.login("admin@fieldsight.demo", "DemoPass123!")
print(client.sync_device("edge-03"))
