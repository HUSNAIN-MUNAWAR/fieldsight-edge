# Authentication and RBAC

`/api/v1/auth/login` creates tracked access and refresh tokens. `get_context` resolves the active workspace from `X-FieldSight-Workspace`, confirms membership, then applies role permissions server-side. `org_item` returns 404 for cross-tenant records to avoid existence leakage. Roles are Platform Admin, Organization Admin, Inspection Manager, Field Operator, Reviewer, Maintenance Coordinator, Data Scientist, and Viewer. Frontend controls are supplemental; the API is authoritative.
