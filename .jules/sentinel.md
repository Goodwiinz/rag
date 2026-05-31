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

## 2024-05-24 - API Information Disclosure via HTTPException
**Vulnerability:** Raw exception details (`str(e)`) were being leaked to clients through `HTTPException` detail fields across multiple document management API endpoints.
**Learning:** Returning `str(e)` directly to users can expose sensitive internal system details, database schemas, or infrastructure layout.
**Prevention:** Always log the full exception on the server using `logger.error("...", exc_info=True)` and return a generic, non-revealing error message to the client (e.g., "Internal server error" or "Failed to upload file").
