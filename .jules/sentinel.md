## 2024-05-18 - Prevent Sensitive Information Disclosure in Error Messages
**Vulnerability:** HTTP 500 error handlers across various modules were returning the raw exception string to the client (`raise HTTPException(status_code=500, detail=str(e))`). This could leak sensitive internal database schemas, credentials, or other system details when an unexpected exception occurs.
**Learning:** Returning `str(e)` in an HTTPException allows arbitrary internal Python exceptions to propagate their exact details to the end-user API response. While useful for debugging, this is a significant information disclosure risk in production systems.
**Prevention:** Always catch exceptions, log the detailed `str(e)` on the server-side, and return a generic, static error message to the client, such as "Internal server error".

## 2025-05-09 - Information Disclosure via HTTPException Detail
**Vulnerability:** API endpoints (e.g. API keys management) were leaking raw database/application exceptions to the client by passing `str(e)` directly into `HTTPException(status_code=500, detail=f"... {str(e)}")`.
**Learning:** Developers frequently pass exception details to the frontend to aid debugging, which inadvertently exposes internal architecture (like SQL statements, file paths, or third-party API errors) to potential attackers.
**Prevention:** Never pass raw exception strings to the client in HTTP response details, especially for 500 Internal Server Errors. Always log the actual exception securely on the server (`logger.error(e)`) and return a sanitized, generic error message (e.g., "Internal server error") to the user.

## 2025-05-18 - Information Disclosure via HTTPException Detail in Security Operations
**Vulnerability:** Exception handlers in `backend/src/api/security/encryption.py` were returning raw exception details (e.g., `str(e)`) to the client inside HTTP 500 error responses (e.g., `raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")`).
**Learning:** Returning exception details from security-sensitive operations like data decryption and key rotation could expose critical details regarding the cryptographic environment, database state, or execution context. This defeats the purpose of returning a 500 error by leaking internal implementation specifics.
**Prevention:** Always log detailed exceptions on the server-side using the `logging` module and return generic, non-descriptive error messages (e.g., "Internal server error") for HTTP 500 responses.

## 2025-06-03 - Prevent Information Disclosure via HTTPException Detail
**Vulnerability:** Several backend API endpoints in modules like search, research, and documents were directly interpolating the raw exception string into 500 Internal Server Error details (e.g., `raise HTTPException(status_code=500, detail=f"Failed to...: {str(e)}")`). This exposed internal system details, potential stack traces, or database errors to the end-user.
**Learning:** Over-informative HTTP exception messages provide debugging convenience at the cost of security, allowing attackers to infer backend structure, queries, or third-party service issues from the client side.
**Prevention:** Always rely on secure server-side logging for detailed exceptions (`logger.error(e)`) and return generic, uninformative messages like "Internal server error" in the `detail` parameter of 500 error responses sent to the client.
## 2026-06-28 - Prevent Information Disclosure in Authentication Exception Handlers
**Vulnerability:** Raw exception strings (`str(e)`) were being passed directly into the `detail` parameter of `HTTPException` for 400 responses across all core authentication endpoints (`/change-password`, `/users/{id}/role`, `/update-profile`, etc.).
**Learning:** This generic catch-all pattern existed to quickly bubble up errors from the service layer to the client. However, because it caught the base `Exception` class, any unexpected error (like database connection failures, parsing errors, or syntax errors) would leak sensitive system details or stack traces to the end user.
**Prevention:** Implement bifurcated exception handling for HTTP endpoints. explicitly catch safe, expected domain exceptions (e.g., `AuthenticationError`, `RegistrationError`) to return specific error messages. Catch the base `Exception` separately to log the raw error securely and return a static, generic error message (e.g., "An error occurred while processing the request") to the client.

## 2024-07-01 - Prevent Information Disclosure in Research Export Exceptions
**Vulnerability:** HTTP 500 error handlers in the `backend/src/api/research/export.py` module were returning the raw exception string to the client (`raise HTTPException(status_code=500, detail=f"Export failed: {e}")`). This leaks internal implementation specifics such as file paths, database constraints, or third-party service errors.
**Learning:** Over-informative HTTP exception messages provide debugging convenience at the cost of security, allowing attackers to infer backend structure or state from the client side.
**Prevention:** Rely on secure server-side logging for detailed exceptions (`logger.error(e)`) and return generic, non-descriptive messages like "Export failed" in the `detail` parameter of 500 error responses sent to the client.
## 2024-08-05 - Fix Bandit B608 (SQL Injection) via SQLAlchemy Core
**Vulnerability:** Raw SQL execution constructed using f-strings with table names (`text(f"SELECT COUNT(*) FROM {tbl} WHERE thread_id = :tid")`).
**Learning:** While the table names were hardcoded in an internal allowlist (rendering it technically safe and bypassed via `# noqa: S608`), constructing raw f-string SQL queries triggers security linters (Bandit) and sets a dangerous precedent. If the internal allowlist was ever modified to accept user input, it would result in a critical SQL injection vulnerability.
**Prevention:** Always use native SQLAlchemy Core components (`table('name', column('col_name'))` combined with `select` or `delete`) instead of raw f-strings when dynamically constructing queries.
