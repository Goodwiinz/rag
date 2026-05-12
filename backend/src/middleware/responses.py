from typing import Dict, Optional

from starlette.responses import JSONResponse


def error_response(
    status_code: int,
    message: str,
    error_type: str = "http_error",
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "status_code": status_code,
                "type": error_type,
            }
        },
        headers=headers,
    )
