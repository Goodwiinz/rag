## 2026-05-24 - Missing Authorization / IDOR in API Key Endpoints

**Vulnerability:** The API Key Management endpoints in `backend/src/api/auth/api_keys.py` were restricted to users with the `ADMIN` role (`Depends(require_admin)`). However, they did not enforce tenant isolation in their SQLAlchemy queries. An admin from one organization could fetch, update, delete, or regenerate an API key belonging to *another* organization simply by providing the target `api_key_id`. Furthermore, the listing and summary endpoints returned all keys across the entire system.

**Learning:** Role-based access control (RBAC) decorators like `require_admin` only verify that the user has the required role within *their own* organization context. They do *not* automatically apply row-level security or tenant filtering to database queries executed within the endpoint.

**Prevention:**
1. Always append a tenant isolation filter (e.g., `.filter(Model.organization_id == str(current_user.organization_id))`) to SQLAlchemy queries when retrieving or modifying objects in a multi-tenant system, even if the endpoint requires admin privileges.
2. In multi-tenant environments, write integration tests that attempt to access or modify resources belonging to a different tenant using valid credentials from the primary tenant.
