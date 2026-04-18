# NOUS CLI Browser Auth Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Claude Code style browser login flow for the NOUS CLI so users can run `./nous login` or `/login` in the REPL and authenticate via the existing web app without downloading a token file manually.

**Architecture:** Add short-lived backend CLI auth sessions under `/api/v1/cli-auth`, build a small `/cli-auth` approval page in the Next app, and extend the CLI to open the browser, poll for approval, and persist the resulting credentials to `~/.nous/auth.json`. Keep the current auth-file loader as the persistence layer and leave the temporary download-file bridge as a fallback during rollout.

**Tech Stack:** FastAPI, existing JWT auth, Redis/in-memory session storage, Next.js App Router, Python asyncio, Python `webbrowser`, pytest, Jest

**Design doc:** `docs/plans/2026-03-27-nous-cli-browser-auth-design.md`

---

## Task 1: Add CLI Auth Session Store

**Files:**
- Create: `backend/src/services/auth/cli_auth_sessions.py`
- Test: `backend/tests/unit/auth/test_cli_auth_sessions.py`

**Step 1: Write the failing test**

```python
from src.services.auth.cli_auth_sessions import InMemoryCLIAuthSessionStore


def test_inmemory_store_round_trips_pending_and_approved_sessions():
    store = InMemoryCLIAuthSessionStore()
    session = store.create_session()
    fetched = store.get_session(session.session_id, session.poll_token)

    assert fetched.status == "pending"

    store.approve_session(
        session.session_id,
        verification_code=session.verification_code,
        user_id="user-1",
        credential_payload={"token": "tok", "organization_id": "org-1"},
    )

    approved = store.get_session(session.session_id, session.poll_token)
    assert approved.status == "approved"
    assert approved.credential_payload["token"] == "tok"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/auth/test_cli_auth_sessions.py -v`
Expected: FAIL with missing module or missing class

**Step 3: Write minimal implementation**

Create an in-memory store with:

- `create_session()`
- `get_session(session_id, poll_token)`
- `approve_session(session_id, verification_code, user_id, credential_payload)`
- `deny_session(...)`
- `expire_session(...)`

Include generated:

- `session_id`
- `poll_token`
- `verification_code`
- `expires_at`
- `status`

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/auth/test_cli_auth_sessions.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/auth/cli_auth_sessions.py backend/tests/unit/auth/test_cli_auth_sessions.py
git commit -m "feat(cli-auth): add in-memory cli auth session store"
```

---

## Task 2: Add Backend CLI Auth Endpoints

**Files:**
- Create: `backend/src/api/auth/cli_auth.py`
- Modify: `backend/src/api/auth/__init__.py`
- Modify: `backend/src/main.py`
- Test: `backend/tests/unit/api/test_cli_auth_routes.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from src.main import app


def test_cli_auth_start_returns_session_and_browser_url():
    client = TestClient(app)
    response = client.post("/api/v1/cli-auth/start")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert body["verification_code"]
    assert "/cli-auth?" in body["browser_url"]
    assert body["poll_token"]
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/api/test_cli_auth_routes.py -v`
Expected: FAIL with 404 or import error

**Step 3: Write minimal implementation**

Add router endpoints:

- `POST /api/v1/cli-auth/start`
- `GET /api/v1/cli-auth/status/{session_id}`
- `POST /api/v1/cli-auth/approve`

Wire the router through `backend/src/api/auth/__init__.py` and `backend/src/main.py`.

For v1, inject the in-memory store from Task 1 directly. Return `session_id`, `verification_code`, `browser_url`, `poll_token`, and expiry metadata from `start`.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/api/test_cli_auth_routes.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/api/auth/cli_auth.py backend/src/api/auth/__init__.py backend/src/main.py backend/tests/unit/api/test_cli_auth_routes.py
git commit -m "feat(cli-auth): add browser auth start and status endpoints"
```

---

## Task 3: Require Authenticated Browser Approval

**Files:**
- Modify: `backend/src/api/auth/cli_auth.py`
- Test: `backend/tests/unit/api/test_cli_auth_approval.py`

**Step 1: Write the failing test**

```python
def test_cli_auth_approve_requires_authenticated_user(client):
    response = client.post(
        "/api/v1/cli-auth/approve",
        json={"session_id": "missing", "verification_code": "bad"},
    )

    assert response.status_code in {401, 403}
```

Also add a second test that mocks an authenticated user and asserts approval flips status to `approved` and stores `token` + `organization_id`.

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/api/test_cli_auth_approval.py -v`
Expected: FAIL because approval endpoint or auth dependency is missing

**Step 3: Write minimal implementation**

In `approve`:

- depend on `get_current_user`
- validate `session_id` + `verification_code`
- mint CLI credential payload using the existing backend token creation utilities
- store `token`, `organization_id`, `user_email`, `expires_at`
- mark the session `approved`

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/api/test_cli_auth_approval.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/api/auth/cli_auth.py backend/tests/unit/api/test_cli_auth_approval.py
git commit -m "feat(cli-auth): require browser approval and mint cli credentials"
```

---

## Task 4: Add Frontend `/cli-auth` Approval Page

**Files:**
- Create: `frontend/app/(auth)/cli-auth/page.tsx`
- Test: `frontend/src/components/auth/__tests__/CliAuthPage.test.tsx`

**Step 1: Write the failing test**

```tsx
import { render, screen } from '@testing-library/react';
import CliAuthPage from '../../../../app/(auth)/cli-auth/page';


test('shows approve action for authenticated browser session', async () => {
  render(<CliAuthPage />);
  expect(await screen.findByRole('button', { name: /approve cli login/i })).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npx jest --runInBand --runTestsByPath src/components/auth/__tests__/CliAuthPage.test.tsx --modulePathIgnorePatterns='<rootDir>/.next'`
Expected: FAIL because the page does not exist

**Step 3: Write minimal implementation**

Create a page that:

- reads `session_id` and `code` from search params
- checks `useAuth()`
- if not authenticated, redirects to `/login` with return params
- if authenticated, renders `Approve CLI login` and `Cancel`

Do not style heavily beyond matching the existing login theme.

**Step 4: Run test to verify it passes**

Run: `cd frontend && npx jest --runInBand --runTestsByPath src/components/auth/__tests__/CliAuthPage.test.tsx --modulePathIgnorePatterns='<rootDir>/.next'`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/app/(auth)/cli-auth/page.tsx frontend/src/components/auth/__tests__/CliAuthPage.test.tsx
git commit -m "feat(cli-auth): add frontend approval page for browser login"
```

---

## Task 5: Wire Frontend Approval To Backend

**Files:**
- Modify: `frontend/app/(auth)/cli-auth/page.tsx`
- Modify: `frontend/src/services/apiClient.ts`
- Test: `frontend/src/components/auth/__tests__/CliAuthPage.test.tsx`

**Step 1: Write the failing test**

Add a test that clicking `Approve CLI login` calls the backend approval endpoint and then shows `CLI connected, return to terminal`.

**Step 2: Run test to verify it fails**

Run: `cd frontend && npx jest --runInBand --runTestsByPath src/components/auth/__tests__/CliAuthPage.test.tsx --modulePathIgnorePatterns='<rootDir>/.next'`
Expected: FAIL because no approval request is made

**Step 3: Write minimal implementation**

Use the existing authenticated frontend API client to:

- `POST /api/v1/cli-auth/approve`
- send `session_id` and `verification_code`
- show success/failure states in the page

**Step 4: Run test to verify it passes**

Run: `cd frontend && npx jest --runInBand --runTestsByPath src/components/auth/__tests__/CliAuthPage.test.tsx --modulePathIgnorePatterns='<rootDir>/.next'`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/app/(auth)/cli-auth/page.tsx frontend/src/services/apiClient.ts frontend/src/components/auth/__tests__/CliAuthPage.test.tsx
git commit -m "feat(cli-auth): connect approval page to backend auth endpoint"
```

---

## Task 6: Add CLI Browser Login Helper And Auth Writer

**Files:**
- Create: `backend/src/cli/browser_auth.py`
- Modify: `backend/src/cli/auth_loader.py`
- Test: `backend/tests/unit/cli/test_browser_auth.py`

**Step 1: Write the failing test**

```python
from pathlib import Path
from src.cli.browser_auth import write_cli_auth_file


def test_write_cli_auth_file_persists_token_and_org(tmp_path: Path):
    target = tmp_path / "auth.json"
    write_cli_auth_file(
        target,
        {
            "token": "tok",
            "organization_id": "org-1",
            "user_email": "admin@example.com",
        },
    )

    assert target.exists()
    assert '"organization_id": "org-1"' in target.read_text()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/cli/test_browser_auth.py -v`
Expected: FAIL with missing module/function

**Step 3: Write minimal implementation**

Create helpers to:

- open browser URL via `webbrowser.open`
- write approved credential payload to `~/.nous/auth.json`
- optionally expose a `delete_cli_auth_file()` helper for future `/logout`

Reuse `auth_loader.py` for the on-disk JSON shape.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/cli/test_browser_auth.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/cli/browser_auth.py backend/src/cli/auth_loader.py backend/tests/unit/cli/test_browser_auth.py
git commit -m "feat(cli): add browser auth helpers and auth file persistence"
```

---

## Task 7: Add `./nous login`

**Files:**
- Modify: `backend/src/cli/agent_chat_cli.py`
- Modify: `backend/nous`
- Test: `backend/tests/unit/cli/test_agent_chat_cli_login.py`

**Step 1: Write the failing test**

```python
def test_main_supports_login_subcommand(monkeypatch):
    from src.cli import agent_chat_cli as cli

    called = {}

    async def fake_login(**kwargs):
        called.update(kwargs)
        return 0

    monkeypatch.setattr(cli, "run_login_flow", fake_login)

    exit_code = cli.main(["login", "--base-url", "http://localhost:8000"])

    assert exit_code == 0
    assert called["base_url"] == "http://localhost:8000"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_chat_cli_login.py -v`
Expected: FAIL because no `login` subcommand exists

**Step 3: Write minimal implementation**

Refactor `main()` to support subcommands:

- `chat` (default)
- `login`

Implement `run_login_flow()` to:

- call `POST /api/v1/cli-auth/start`
- open browser or print URL
- poll status until approved/denied/expired
- write `~/.nous/auth.json` on success

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_chat_cli_login.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/cli/agent_chat_cli.py backend/nous backend/tests/unit/cli/test_agent_chat_cli_login.py
git commit -m "feat(cli): add top-level nous login browser auth flow"
```

---

## Task 8: Add `/login` To The REPL

**Files:**
- Modify: `backend/src/cli/agent_chat_cli.py`
- Test: `backend/tests/unit/cli/test_agent_chat_cli_commands.py`
- Test: `backend/tests/unit/cli/test_agent_chat_cli_stream_flow.py`

**Step 1: Write the failing test**

```python
def test_apply_command_login_returns_login_signal():
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state, output = apply_command(CLISessionState(), "/login")

    assert output == "LOGIN_REQUESTED"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_chat_cli_commands.py -v -k login`
Expected: FAIL because `/login` is unknown

**Step 3: Write minimal implementation**

Add `/login` to help text and command parsing. In the REPL loop:

- intercept the login signal
- run the same login flow as the top-level subcommand
- resume the existing session state without dropping the REPL

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_chat_cli_commands.py tests/unit/cli/test_agent_chat_cli_stream_flow.py -v -k login`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/cli/agent_chat_cli.py backend/tests/unit/cli/test_agent_chat_cli_commands.py backend/tests/unit/cli/test_agent_chat_cli_stream_flow.py
git commit -m "feat(cli): add in-session login command"
```

---

## Task 9: Replace Stack Traces With Friendly Auth Errors

**Files:**
- Modify: `backend/src/cli/agent_api_client.py`
- Modify: `backend/src/cli/agent_chat_cli.py`
- Test: `backend/tests/unit/cli/test_agent_api_client.py`

**Step 1: Write the failing test**

```python
def test_auth_failures_render_friendly_message_instead_of_raw_stacktrace():
    ...
```

Assert that `401/403` during login or agent streaming become compact auth messages like:

- `auth> login required`
- `auth> saved credentials rejected`

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_api_client.py -v -k auth`
Expected: FAIL because the CLI raises raw `HTTPStatusError`

**Step 3: Write minimal implementation**

Catch auth-related `httpx.HTTPStatusError` in the CLI path and convert them to readable terminal messages. Keep full stack traces behind `--debug`.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/cli/test_agent_api_client.py -v -k auth`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/cli/agent_api_client.py backend/src/cli/agent_chat_cli.py backend/tests/unit/cli/test_agent_api_client.py
git commit -m "feat(cli): show friendly auth failures during browser login flow"
```

---

## Task 10: Final Verification And Transition

**Files:**
- Modify: `docs/plans/2026-03-27-nous-cli-browser-auth-design.md`
- Modify: `docs/plans/2026-03-27-nous-cli-browser-auth-plan.md`

**Step 1: Run focused backend tests**

Run:

```bash
cd backend
python -m pytest \
  tests/unit/auth/test_cli_auth_sessions.py \
  tests/unit/api/test_cli_auth_routes.py \
  tests/unit/api/test_cli_auth_approval.py \
  tests/unit/cli/test_browser_auth.py \
  tests/unit/cli/test_agent_chat_cli_login.py \
  tests/unit/cli/test_agent_chat_cli_commands.py \
  tests/unit/cli/test_agent_api_client.py -v
```

Expected: PASS

**Step 2: Run focused frontend tests**

Run:

```bash
cd frontend
npx jest --runInBand \
  --runTestsByPath \
  src/components/auth/__tests__/CliAuthPage.test.tsx \
  --modulePathIgnorePatterns='<rootDir>/.next'
```

Expected: PASS

**Step 3: Run manual flow**

1. `./nous login`
2. browser opens `/cli-auth`
3. approve in browser
4. CLI stores `~/.nous/auth.json`
5. run `./nous` and verify auth is reused automatically

**Step 4: Update docs if behavior changed during implementation**

Keep the design doc and plan accurate if endpoint names, payload fields, or CLI output wording drifted during implementation.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-27-nous-cli-browser-auth-design.md docs/plans/2026-03-27-nous-cli-browser-auth-plan.md
git commit -m "docs(cli-auth): finalize browser login implementation notes"
```
