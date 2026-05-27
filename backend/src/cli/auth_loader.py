from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ResolvedCLIAuth:
    token: str = ""
    organization_id: str = ""
    source_path: Path | None = None


def default_cli_auth_path() -> Path:
    return Path.home() / ".nous" / "auth.json"


def save_cli_auth(
    *,
    token: str,
    organization_id: str,
    user_email: str = "",
    expires_at: str = "",
    auth_path: Path | None = None,
) -> Path:
    target_path = auth_path or default_cli_auth_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "source": "cli-browser-login",
        "exported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "token": token,
        "organization_id": organization_id,
    }
    if user_email:
        payload["user_email"] = user_email
    if expires_at:
        payload["expires_at"] = expires_at

    target_path.write_text(json.dumps(payload, indent=2))
    target_path.chmod(0o600)
    return target_path


def write_cli_auth_payload(
    payload: dict[str, Any],
    auth_path: Path | None = None,
) -> Path:
    return save_cli_auth(
        token=str(payload.get("token") or payload.get("access_token") or ""),
        organization_id=str(payload.get("organization_id") or ""),
        user_email=str(payload.get("user_email") or ""),
        expires_at=str(payload.get("expires_at") or ""),
        auth_path=auth_path,
    )


def _load_auth_payload(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        return {}
    return data


def _extract_token(payload: dict[str, Any]) -> str:
    token = payload.get("token") or payload.get("access_token") or ""
    return str(token) if token else ""


def _extract_organization_id(payload: dict[str, Any]) -> str:
    organization_id = payload.get("organization_id") or ""
    if organization_id:
        return str(organization_id)

    organization = payload.get("organization")
    if isinstance(organization, dict) and organization.get("id"):
        return str(organization["id"])

    return ""


def _download_exports(home_dir: Path) -> list[Path]:
    downloads_dir = home_dir / "Downloads"
    if not downloads_dir.exists():
        return []

    exports = list(downloads_dir.glob("nous-auth*.json"))
    return sorted(exports, key=lambda item: item.stat().st_mtime, reverse=True)


def _candidate_auth_paths(auth_file: str) -> list[Path]:
    if auth_file:
        return [Path(auth_file).expanduser()]

    home_dir = Path.home()
    candidates: list[Path] = []
    persistent_auth = home_dir / ".nous" / "auth.json"
    if persistent_auth.exists():
        candidates.append(persistent_auth)
    candidates.extend(_download_exports(home_dir))
    return candidates


def resolve_cli_auth(
    *,
    token: str,
    organization_id: str,
    auth_file: str = "",
) -> ResolvedCLIAuth:
    resolved_token = token
    resolved_organization_id = organization_id
    source_path: Path | None = None

    for path in _candidate_auth_paths(auth_file):
        if not path.exists() or not path.is_file():
            continue

        try:
            payload = _load_auth_payload(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue

        file_token = _extract_token(payload)
        file_organization_id = _extract_organization_id(payload)
        if not file_token and not file_organization_id:
            continue

        if not resolved_token:
            resolved_token = file_token
        if not resolved_organization_id:
            resolved_organization_id = file_organization_id
        source_path = path
        break

    return ResolvedCLIAuth(
        token=resolved_token,
        organization_id=resolved_organization_id,
        source_path=source_path,
    )
