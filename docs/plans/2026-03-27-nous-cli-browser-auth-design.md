# NOUS CLI Browser Auth Design

**Date:** 2026-03-27  
**Branch:** `codex/agent-chat-cli`  
**Approach:** Backend-mediated browser login flow shared by `./nous login` and in-REPL `/login`

---

## Decisions

| Decision | Choice |
| --- | --- |
| Primary UX | Support both `./nous login` and `/login` inside the REPL |
| Browser handoff | Open the existing web app in the default browser |
| Trust boundary | Browser session authenticates user, backend mints CLI credentials |
| CLI credential reuse | Store local credentials in `~/.nous/auth.json` |
| Backend session storage | Redis when available, short-lived in-memory fallback for dev |
| Current file export flow | Keep only as a temporary fallback during transition |

---

## 1. Goal

Replace the temporary download-file auth bridge with a Claude Code style browser login flow for the NOUS CLI:

1. run `./nous` or `./nous login`
2. type `/login` if needed
3. browser opens to the NOUS web app
4. user signs in or reuses an existing browser session
5. user approves the CLI connection
6. CLI becomes authenticated automatically and resumes

The CLI should not require manual token flags, header copying, or browser storage scraping.

---

## 2. Existing Context

The current CLI already supports local auth reuse via `--auth-file` and `~/.nous/auth.json` / `~/Downloads/nous-auth*.json` through `backend/src/cli/auth_loader.py`.

The web app login route is the App Router page at `frontend/app/(auth)/login/page.tsx`.

The agent API already uses standard bearer auth through `backend/src/core/security.py` and `backend/src/core/dependencies.py`, so the cleanest v1 is to mint a CLI credential that the existing backend auth dependencies already accept.

---

## 3. UX

### Shell entrypoint

```text
$ ./nous
auth> not signed in
auth> run /login to connect this CLI
nous>
```

```text
$ ./nous login
auth> opening browser for NOUS CLI sign-in...
auth> visit: http://localhost:3000/cli-auth?session_id=...&code=...
auth> waiting for approval...
auth> signed in as admin@multimodal-rag.com
```

### In-REPL flow

```text
nous> /login
auth> opening browser for NOUS CLI sign-in...
auth> waiting for approval...
auth> signed in as admin@multimodal-rag.com
nous>
```

Both entrypoints should use the same backend session flow and the same local credential storage.

---

## 4. Architecture

### Backend

Add a dedicated CLI auth router under the normal API surface:

- `POST /api/v1/cli-auth/start`
- `GET /api/v1/cli-auth/status/{session_id}`
- `POST /api/v1/cli-auth/approve`

The backend owns the trust boundary:

- browser session proves the human user
- CLI proves possession of the short-lived session id + polling secret
- backend mints CLI credentials only after explicit approval

### Frontend

Add a `/cli-auth` approval page:

- if the user is not signed in, redirect to `/login` and back
- if signed in, show CLI approval UI
- submitting approval calls the backend approval endpoint
- success page tells the user to return to the terminal

### CLI

Extend the CLI to:

- support a top-level `login` subcommand
- support `/login` in the REPL
- open the browser via Python `webbrowser`
- poll backend auth session status
- write credentials to `~/.nous/auth.json`

---

## 5. Auth Protocol

### Start

`POST /api/v1/cli-auth/start`

Returns:

```json
{
  "session_id": "...",
  "verification_code": "ABCD-1234",
  "browser_url": "http://localhost:3000/cli-auth?session_id=...&code=...",
  "poll_token": "...",
  "expires_at": "2026-03-27T12:34:56Z",
  "poll_interval_seconds": 2
}
```

### Status

`GET /api/v1/cli-auth/status/{session_id}`

Returns one of:

- `pending`
- `approved`
- `denied`
- `expired`
- `cancelled`

If `approved`, return CLI credentials and identity metadata:

```json
{
  "status": "approved",
  "token": "...",
  "organization_id": "...",
  "user_email": "admin@multimodal-rag.com",
  "expires_at": "2026-03-27T20:34:56Z"
}
```

### Approve

`POST /api/v1/cli-auth/approve`

Requires authenticated browser user. Validates `session_id` + `verification_code`, then marks the session approved and stores the minted CLI credential payload for the polling client.

---

## 6. Session Storage

For v1:

- use Redis when available
- use short-lived in-memory storage when Redis is unavailable and the app is running in a single process

Session payload should include:

- `session_id`
- `poll_token`
- `verification_code`
- `created_at`
- `expires_at`
- `status`
- `user_id` when approved
- final CLI credential payload when approved

Sessions should expire quickly, ideally 5 minutes.

---

## 7. Security Model

- CLI never reads browser local storage or cookies directly
- approval requires explicit browser action
- `session_id` alone is not enough for polling; use a second secret like `poll_token`
- approval is one-time use only
- CLI credentials can reuse the existing backend JWT shape for v1
- tag or annotate minted tokens as `source=cli` for observability if possible

This keeps the implementation aligned with the current backend auth stack while still distinguishing CLI-originated sessions.

---

## 8. Failure Handling

CLI behavior should be explicit:

- if browser opening fails, print the URL and code
- if status becomes `denied`, print `auth> login denied in browser`
- if status becomes `expired`, print `auth> login session expired`
- if the backend is unavailable, print a short error without a Python stack trace by default

Frontend behavior:

- if the user is not logged in, preserve the pending CLI session across redirect to `/login`
- if approval fails, show a retryable error state
- if the session is already expired, show a terminal-friendly explanation rather than a generic app error

---

## 9. Testing

### Backend

- session store lifecycle
- start/status/approve route behavior
- approval requires authenticated user
- approval and polling expiry behavior
- minted CLI token payload shape

### Frontend

- `/cli-auth` redirect when unauthenticated
- approval page render when authenticated
- approve/cancel flows
- redirect back from `/login` to `/cli-auth`

### CLI

- `./nous login` opens browser and polls
- `/login` works inside the REPL
- approved sessions persist to `~/.nous/auth.json`
- denied/expired flows print friendly messages

---

## 10. Rollout

Roll out in this order:

1. backend session store and routes
2. frontend `/cli-auth` page
3. CLI `login` subcommand
4. REPL `/login`
5. de-emphasize the download-file bridge

Keep the export-file auth path temporarily so existing work is not blocked during the transition.
