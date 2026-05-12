## 2024-05-18 - Prevent Sensitive Information Disclosure in Error Messages
**Vulnerability:** HTTP 500 error handlers across various modules were returning the raw exception string to the client (`raise HTTPException(status_code=500, detail=str(e))`). This could leak sensitive internal database schemas, credentials, or other system details when an unexpected exception occurs.
**Learning:** Returning `str(e)` in an HTTPException allows arbitrary internal Python exceptions to propagate their exact details to the end-user API response. While useful for debugging, this is a significant information disclosure risk in production systems.
**Prevention:** Always catch exceptions, log the detailed `str(e)` on the server-side, and return a generic, static error message to the client, such as "Internal server error".

## 2025-05-09 - Information Disclosure via HTTPException Detail
**Vulnerability:** API endpoints (e.g. API keys management) were leaking raw database/application exceptions to the client by passing `str(e)` directly into `HTTPException(status_code=500, detail=f"... {str(e)}")`.
**Learning:** Developers frequently pass exception details to the frontend to aid debugging, which inadvertently exposes internal architecture (like SQL statements, file paths, or third-party API errors) to potential attackers.
**Prevention:** Never pass raw exception strings to the client in HTTP response details, especially for 500 Internal Server Errors. Always log the actual exception securely on the server (`logger.error(e)`) and return a sanitized, generic error message (e.g., "Internal server error") to the user.
