# Multi-tenancy

Every primary operational record contains `organization_id`. Workspace resolution uses `X-FieldSight-Workspace`; membership and role are checked in `get_context`; resource retrieval uses `org_item`. This makes cross-tenant access a backend denial, not a frontend filter. Project/site restrictions are a documented extension point in Membership site restrictions and resource queries.
