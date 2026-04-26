# NOUS CLI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a TypeScript + Ink terminal CLI (`./nous`) that talks to the existing NOUS agent API, supporting interactive REPL and one-shot modes with real-time streaming and tool call display.

**Architecture:** Code lives in `frontend/cli/`, reusing `agentChatService.ts` for streaming. Auth uses the existing backend session flow (`POST /api/v1/cli-auth/start` → open browser → poll `GET /api/v1/cli-auth/status`). Root `./nous` shell script is the user-facing entry point.

**Tech Stack:** TypeScript, Ink 4, React 18, `open` (browser launcher), `tsx` (TS runner), Jest + `ink-testing-library` for tests.

---

## Key File Map (read these before starting)

- `frontend/src/services/agentChatService.ts` — the streaming service to wrap
- `frontend/app/(auth)/cli-auth/page.tsx` — web approval page (already built)
- `backend/src/api/auth/cli_auth.py` — auth backend (`/start`, `/status`, `/approve`)
- `frontend/tsconfig.json` — check path aliases (`@/*` maps to `src/*`)

## Auth API (already built — just consume it)

```
POST /api/v1/cli-auth/start
  → { session_id, verification_code, browser_url, poll_token, expires_at, poll_interval_seconds }

GET /api/v1/cli-auth/status/{session_id}?poll_token=<poll_token>
  → { status: "pending" | "approved" | "expired", token?, organization_id?, user_email? }
```

When `status === "approved"`, save `{ token, organization_id, user_email, expires_at }` to `~/.nous/config.json`.

---

## Phase 1 — Setup

### Task 1: Install dependencies and scaffold directory

**Files:**

- Modify: `frontend/package.json`
- Create: `frontend/cli/` (directory structure)
- Create: `./nous` (repo root shell script)

**Step 1: Install Ink and open**

```bash
cd frontend && pnpm add ink@^4.4.1 open@^10.1.0
```

Expected: `node_modules/ink` and `node_modules/open` appear.

**Step 2: Add `cli` script to `frontend/package.json`**

In the `"scripts"` section, add:

```json
"cli": "tsx cli/index.ts"
```

**Step 3: Create the directory skeleton**

```bash
mkdir -p frontend/cli/auth frontend/cli/components frontend/cli/hooks frontend/cli/services
touch frontend/cli/index.ts
touch frontend/cli/auth/store.ts
touch frontend/cli/auth/deviceFlow.ts
touch frontend/cli/components/App.tsx
touch frontend/cli/components/ChatMessage.tsx
touch frontend/cli/components/ToolCall.tsx
touch frontend/cli/components/StreamingLine.tsx
touch frontend/cli/components/Prompt.tsx
touch frontend/cli/components/StatusBar.tsx
touch frontend/cli/hooks/useStream.ts
touch frontend/cli/hooks/useSlashCommands.ts
touch frontend/cli/services/client.ts
```

**Step 4: Create `./nous` root wrapper**

Create file `./nous` at repo root:

```bash
#!/usr/bin/env bash
set -euo pipefail
exec pnpm --prefix frontend cli "$@"
```

Make it executable:

```bash
chmod +x ./nous
```

**Step 5: Verify scaffold works**

Add to `frontend/cli/index.ts` temporarily:

```typescript
console.log("NOUS CLI");
```

Run:

```bash
./nous
```

Expected output: `NOUS CLI`

**Step 6: Commit**

```bash
git add frontend/package.json frontend/cli/ nous
git commit -m "chore(cli): scaffold TypeScript Ink CLI structure"
```

---

## Phase 2 — Auth Module

### Task 2: Config store (`auth/store.ts`)

**Files:**

- Create: `frontend/cli/auth/store.ts`
- Create: `frontend/cli/__tests__/auth/store.test.ts`

**Step 1: Write failing test**

Create `frontend/cli/__tests__/auth/store.test.ts`:

```typescript
import { existsSync, rmSync } from "fs";
import * as os from "os";
import * as path from "path";

// Override config path for tests
process.env.NOUS_CONFIG_DIR = path.join(
  os.tmpdir(),
  `.nous-test-${Date.now()}`,
);

import {
  loadConfig,
  saveConfig,
  clearConfig,
  NousConfig,
} from "../../auth/store";

afterEach(() => {
  clearConfig();
});

test("returns null when no config exists", () => {
  expect(loadConfig()).toBeNull();
});

test("saves and loads config", () => {
  const config: NousConfig = {
    token: "tok_abc",
    user_email: "test@example.com",
    organization_id: "org_1",
    expires_at: "2099-01-01T00:00:00Z",
    thread_id: null,
  };
  saveConfig(config);
  expect(loadConfig()).toEqual(config);
});

test("clearConfig removes the file", () => {
  saveConfig({
    token: "x",
    user_email: "a@b.com",
    organization_id: "o",
    expires_at: "2099-01-01T00:00:00Z",
    thread_id: null,
  });
  clearConfig();
  expect(loadConfig()).toBeNull();
});
```

**Step 2: Run test to verify it fails**

```bash
cd frontend && pnpm test cli/__tests__/auth/store.test.ts
```

Expected: FAIL — `Cannot find module '../../auth/store'`

**Step 3: Implement `auth/store.ts`**

```typescript
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "fs";
import * as os from "os";
import * as path from "path";

export interface NousConfig {
  token: string;
  user_email: string;
  organization_id: string;
  expires_at: string;
  thread_id: string | null;
}

function configDir(): string {
  return process.env.NOUS_CONFIG_DIR ?? path.join(os.homedir(), ".nous");
}

function configPath(): string {
  return path.join(configDir(), "config.json");
}

export function loadConfig(): NousConfig | null {
  const p = configPath();
  if (!existsSync(p)) return null;
  try {
    return JSON.parse(readFileSync(p, "utf-8")) as NousConfig;
  } catch {
    return null;
  }
}

export function saveConfig(config: NousConfig): void {
  const dir = configDir();
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  writeFileSync(configPath(), JSON.stringify(config, null, 2), "utf-8");
}

export function clearConfig(): void {
  const p = configPath();
  if (existsSync(p)) rmSync(p);
}
```

**Step 4: Run test to verify it passes**

```bash
cd frontend && pnpm test cli/__tests__/auth/store.test.ts
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add frontend/cli/auth/store.ts frontend/cli/__tests__/auth/store.test.ts
git commit -m "feat(cli): add auth config store (read/write ~/.nous/config.json)"
```

---

### Task 3: Device flow login (`auth/deviceFlow.ts`)

**Files:**

- Create: `frontend/cli/auth/deviceFlow.ts`
- Create: `frontend/cli/__tests__/auth/deviceFlow.test.ts`

**Step 1: Write failing test**

```typescript
// frontend/cli/__tests__/auth/deviceFlow.test.ts
import { pollForApproval } from "../../auth/deviceFlow";

test("resolves with token when status becomes approved", async () => {
  let callCount = 0;
  const mockFetch = jest.fn().mockImplementation(() => {
    callCount++;
    const status = callCount >= 3 ? "approved" : "pending";
    const extra =
      status === "approved"
        ? {
            token: "tok_approved",
            user_email: "a@b.com",
            organization_id: "org1",
            expires_at: "2099-01-01T00:00:00Z",
          }
        : {};
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ status, ...extra }),
    });
  });

  const result = await pollForApproval("sess_1", "pt_1", {
    fetchFn: mockFetch as any,
    intervalMs: 0,
  });
  expect(result.token).toBe("tok_approved");
  expect(callCount).toBe(3);
});

test("rejects when status is expired", async () => {
  const mockFetch = jest.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ status: "expired" }),
  });
  await expect(
    pollForApproval("sess_1", "pt_1", {
      fetchFn: mockFetch as any,
      intervalMs: 0,
    }),
  ).rejects.toThrow("expired");
});
```

**Step 2: Run test to verify it fails**

```bash
cd frontend && pnpm test cli/__tests__/auth/deviceFlow.test.ts
```

Expected: FAIL — module not found

**Step 3: Implement `auth/deviceFlow.ts`**

```typescript
import { loadConfig, saveConfig } from "./store";

const BACKEND_URL = process.env.NOUS_API_URL ?? "http://localhost:8000/api/v1";

interface PollOptions {
  fetchFn?: typeof fetch;
  intervalMs?: number;
}

export interface ApprovalResult {
  token: string;
  user_email: string;
  organization_id: string;
  expires_at: string;
}

export async function startCliAuth(): Promise<{
  session_id: string;
  poll_token: string;
  browser_url: string;
  poll_interval_seconds: number;
}> {
  const res = await fetch(`${BACKEND_URL}/cli-auth/start`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to start CLI auth: ${res.status}`);
  return res.json();
}

export async function pollForApproval(
  session_id: string,
  poll_token: string,
  { fetchFn = fetch, intervalMs }: PollOptions = {},
): Promise<ApprovalResult> {
  const url = `${BACKEND_URL}/cli-auth/status/${encodeURIComponent(session_id)}?poll_token=${encodeURIComponent(poll_token)}`;

  while (true) {
    const res = await fetchFn(url);
    if (!res.ok) throw new Error(`Poll failed: ${res.status}`);
    const data = await res.json();

    if (data.status === "approved") {
      return {
        token: data.token,
        user_email: data.user_email,
        organization_id: data.organization_id,
        expires_at: data.expires_at,
      };
    }
    if (data.status === "expired") {
      throw new Error("Login session expired. Run ./nous login again.");
    }

    const delay = intervalMs ?? 2000;
    if (delay > 0) await new Promise((r) => setTimeout(r, delay));
  }
}

export async function login(): Promise<void> {
  const { session_id, poll_token, browser_url } = await startCliAuth();

  // Dynamic import so non-login paths don't load open
  const { default: open } = await import("open");
  await open(browser_url);

  console.log("\nOpening browser for authorization...");
  console.log(`If browser did not open, visit:\n  ${browser_url}\n`);

  const result = await pollForApproval(session_id, poll_token);

  saveConfig({
    token: result.token,
    user_email: result.user_email,
    organization_id: result.organization_id,
    expires_at: result.expires_at,
    thread_id: null,
  });

  console.log(`\n✓ Logged in as ${result.user_email}`);
}

export function isTokenExpired(expiresAt: string): boolean {
  return new Date(expiresAt).getTime() < Date.now();
}
```

**Step 4: Run test to verify it passes**

```bash
cd frontend && pnpm test cli/__tests__/auth/deviceFlow.test.ts
```

Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add frontend/cli/auth/deviceFlow.ts frontend/cli/__tests__/auth/deviceFlow.test.ts
git commit -m "feat(cli): add device-flow auth (poll-based, no local server)"
```

---

## Phase 3 — Service Client

### Task 4: CLI service client (`services/client.ts`)

The CLI needs to inject the auth token into every request. `agentChatService.ts` reads from Supabase session — the CLI can't use that. Instead, override the header-injection function.

**Files:**

- Create: `frontend/cli/services/client.ts`
- Create: `frontend/cli/__tests__/services/client.test.ts`

**Step 1: Write failing test**

```typescript
// frontend/cli/__tests__/services/client.test.ts
import * as store from "../../auth/store";
import { getCliAuthHeaders } from "../../services/client";

test("returns Authorization header when token is present", () => {
  jest.spyOn(store, "loadConfig").mockReturnValue({
    token: "tok_test",
    user_email: "x@y.com",
    organization_id: "org_1",
    expires_at: "2099-01-01T00:00:00Z",
    thread_id: null,
  });
  const headers = getCliAuthHeaders();
  expect(headers["Authorization"]).toBe("Bearer tok_test");
  expect(headers["X-Organization-ID"]).toBe("org_1");
});

test("throws when not logged in", () => {
  jest.spyOn(store, "loadConfig").mockReturnValue(null);
  expect(() => getCliAuthHeaders()).toThrow("Not logged in");
});
```

**Step 2: Run test to verify it fails**

```bash
cd frontend && pnpm test cli/__tests__/services/client.test.ts
```

Expected: FAIL — module not found

**Step 3: Implement `services/client.ts`**

```typescript
import { loadConfig } from "../auth/store";

export function getCliAuthHeaders(): Record<string, string> {
  const config = loadConfig();
  if (!config) throw new Error("Not logged in. Run: ./nous login");
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${config.token}`,
    "X-Organization-ID": config.organization_id,
  };
}

export const API_BASE =
  process.env.NOUS_API_URL ?? "http://localhost:8000/api/v1";

// Re-export the streaming callbacks type from the frontend service
export type { AgentExecuteRequest } from "../../src/services/agentChatService";
```

**Step 4: Run test to verify it passes**

```bash
cd frontend && pnpm test cli/__tests__/services/client.test.ts
```

Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add frontend/cli/services/client.ts frontend/cli/__tests__/services/client.test.ts
git commit -m "feat(cli): add CLI service client with auth header injection"
```

---

## Phase 4 — Ink Components

> Ink components render to the terminal using React. Test them with `@inkjs/ui` patterns or `ink-testing-library`. Each component is pure — receive props, render boxes/text.

### Task 5: `<StatusBar>` and `<ChatMessage>` components

**Files:**

- Create: `frontend/cli/components/StatusBar.tsx`
- Create: `frontend/cli/components/ChatMessage.tsx`
- Create: `frontend/cli/__tests__/components/StatusBar.test.tsx`
- Create: `frontend/cli/__tests__/components/ChatMessage.test.tsx`

**Step 1: Install ink-testing-library**

```bash
cd frontend && pnpm add -D ink-testing-library
```

**Step 2: Write failing tests**

```typescript
// frontend/cli/__tests__/components/StatusBar.test.tsx
import { render } from 'ink-testing-library';
import React from 'react';
import { StatusBar } from '../../components/StatusBar';

test('shows thread id and project', () => {
  const { lastFrame } = render(
    <StatusBar threadId="thread_abc" projectName="ML Healthcare" citationCount={3} />
  );
  expect(lastFrame()).toContain('thread_abc');
  expect(lastFrame()).toContain('ML Healthcare');
  expect(lastFrame()).toContain('3');
});

test('shows no project when undefined', () => {
  const { lastFrame } = render(
    <StatusBar threadId="t1" projectName={undefined} citationCount={0} />
  );
  expect(lastFrame()).not.toContain('undefined');
});
```

```typescript
// frontend/cli/__tests__/components/ChatMessage.test.tsx
import { render } from 'ink-testing-library';
import React from 'react';
import { ChatMessage } from '../../components/ChatMessage';

test('renders user message with "You" prefix', () => {
  const { lastFrame } = render(<ChatMessage role="user" content="hello" />);
  expect(lastFrame()).toContain('You');
  expect(lastFrame()).toContain('hello');
});

test('renders assistant message with "NOUS" prefix', () => {
  const { lastFrame } = render(<ChatMessage role="assistant" content="hi back" />);
  expect(lastFrame()).toContain('NOUS');
  expect(lastFrame()).toContain('hi back');
});
```

**Step 3: Run tests to verify they fail**

```bash
cd frontend && pnpm test cli/__tests__/components/StatusBar.test.tsx cli/__tests__/components/ChatMessage.test.tsx
```

Expected: FAIL — modules not found

**Step 4: Implement `StatusBar.tsx`**

```typescript
import { Box, Text } from 'ink';
import React from 'react';

interface StatusBarProps {
  threadId: string | null;
  projectName: string | undefined;
  citationCount: number;
}

export function StatusBar({ threadId, projectName, citationCount }: StatusBarProps) {
  return (
    <Box borderStyle="single" borderColor="gray" paddingX={1} justifyContent="space-between">
      <Text color="gray">
        {threadId ? `thread: ${threadId.slice(0, 8)}…` : 'no thread'}
      </Text>
      {projectName && <Text color="cyan"> project: {projectName}</Text>}
      {citationCount > 0 && <Text color="yellow"> {citationCount} citations</Text>}
    </Box>
  );
}
```

**Step 5: Implement `ChatMessage.tsx`**

```typescript
import { Box, Text } from 'ink';
import React from 'react';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
}

export function ChatMessage({ role, content }: ChatMessageProps) {
  const isUser = role === 'user';
  return (
    <Box flexDirection="column" marginY={1}>
      <Text bold color={isUser ? 'green' : 'magenta'}>
        {isUser ? 'You' : 'NOUS'}
      </Text>
      <Text>{content}</Text>
    </Box>
  );
}
```

**Step 6: Run tests to verify they pass**

```bash
cd frontend && pnpm test cli/__tests__/components/StatusBar.test.tsx cli/__tests__/components/ChatMessage.test.tsx
```

Expected: PASS (4 tests)

**Step 7: Commit**

```bash
git add frontend/cli/components/StatusBar.tsx frontend/cli/components/ChatMessage.tsx \
  frontend/cli/__tests__/components/
git commit -m "feat(cli): add StatusBar and ChatMessage Ink components"
```

---

### Task 6: `<ToolCall>` component

**Files:**

- Create: `frontend/cli/components/ToolCall.tsx`
- Create: `frontend/cli/__tests__/components/ToolCall.test.tsx`

**Step 1: Write failing tests**

```typescript
// frontend/cli/__tests__/components/ToolCall.test.tsx
import { render } from 'ink-testing-library';
import React from 'react';
import { ToolCall } from '../../components/ToolCall';

test('shows running state with spinner char', () => {
  const { lastFrame } = render(
    <ToolCall tool="search_arxiv" status="running" durationMs={null} />
  );
  expect(lastFrame()).toContain('search_arxiv');
  expect(lastFrame()).toContain('running');
});

test('shows done state with duration', () => {
  const { lastFrame } = render(
    <ToolCall tool="search_arxiv" status="done" durationMs={820} />
  );
  expect(lastFrame()).toContain('✓');
  expect(lastFrame()).toContain('0.8s');
});

test('shows error state', () => {
  const { lastFrame } = render(
    <ToolCall tool="ingest_arxiv_papers" status="error" durationMs={2100} />
  );
  expect(lastFrame()).toContain('✗');
  expect(lastFrame()).toContain('ingest_arxiv_papers');
});
```

**Step 2: Run test to verify it fails**

```bash
cd frontend && pnpm test cli/__tests__/components/ToolCall.test.tsx
```

Expected: FAIL

**Step 3: Implement `ToolCall.tsx`**

```typescript
import { Box, Text } from 'ink';
import React from 'react';

type ToolStatus = 'running' | 'done' | 'error';

interface ToolCallProps {
  tool: string;
  status: ToolStatus;
  durationMs: number | null;
}

const ICON: Record<ToolStatus, string> = {
  running: '▶',
  done: '✓',
  error: '✗',
};
const COLOR: Record<ToolStatus, string> = {
  running: 'yellow',
  done: 'green',
  error: 'red',
};

export function ToolCall({ tool, status, durationMs }: ToolCallProps) {
  const duration =
    durationMs !== null ? ` (${(durationMs / 1000).toFixed(1)}s)` : '';
  const label = status === 'running' ? 'running…' : status;

  return (
    <Box>
      <Text color={COLOR[status] as any}>{ICON[status]} </Text>
      <Text>{tool.padEnd(28)}</Text>
      <Text color="gray">
        {label}
        {duration}
      </Text>
    </Box>
  );
}
```

**Step 4: Run test to verify it passes**

```bash
cd frontend && pnpm test cli/__tests__/components/ToolCall.test.tsx
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add frontend/cli/components/ToolCall.tsx frontend/cli/__tests__/components/ToolCall.test.tsx
git commit -m "feat(cli): add ToolCall component (running/done/error states)"
```

---

### Task 7: `<StreamingLine>` and `<Prompt>` components

**Files:**

- Create: `frontend/cli/components/StreamingLine.tsx`
- Create: `frontend/cli/components/Prompt.tsx`
- Create: `frontend/cli/__tests__/components/StreamingLine.test.tsx`

**Step 1: Write failing tests**

```typescript
// frontend/cli/__tests__/components/StreamingLine.test.tsx
import { render } from 'ink-testing-library';
import React from 'react';
import { StreamingLine } from '../../components/StreamingLine';

test('renders streaming content with cursor', () => {
  const { lastFrame } = render(<StreamingLine content="Hello world" />);
  expect(lastFrame()).toContain('Hello world');
  expect(lastFrame()).toContain('▋');
});

test('renders nothing when content is empty', () => {
  const { lastFrame } = render(<StreamingLine content="" />);
  expect(lastFrame()).not.toContain('▋');
});
```

**Step 2: Run test to verify it fails**

```bash
cd frontend && pnpm test cli/__tests__/components/StreamingLine.test.tsx
```

Expected: FAIL

**Step 3: Implement `StreamingLine.tsx`**

```typescript
import { Box, Text } from 'ink';
import React from 'react';

interface StreamingLineProps {
  content: string;
}

export function StreamingLine({ content }: StreamingLineProps) {
  if (!content) return null;
  return (
    <Box flexDirection="column" marginY={1}>
      <Text bold color="magenta">NOUS</Text>
      <Text>{content}<Text color="cyan">▋</Text></Text>
    </Box>
  );
}
```

**Step 4: Implement `Prompt.tsx`** (no unit test — relies on Ink's `useInput` which needs a real TTY)

```typescript
import { Box, Text, useInput } from 'ink';
import React, { useState } from 'react';

const SLASH_COMMANDS = ['/new', '/thread', '/context', '/help', '/quit'];

interface PromptProps {
  onSubmit: (input: string) => void;
  disabled?: boolean;
}

export function Prompt({ onSubmit, disabled = false }: PromptProps) {
  const [value, setValue] = useState('');
  const [hint, setHint] = useState('');

  useInput((input, key) => {
    if (disabled) return;

    if (key.return) {
      if (value.trim()) {
        onSubmit(value.trim());
        setValue('');
        setHint('');
      }
      return;
    }

    if (key.backspace || key.delete) {
      const next = value.slice(0, -1);
      setValue(next);
      setHint(getHint(next));
      return;
    }

    const next = value + input;
    setValue(next);
    setHint(getHint(next));
  });

  return (
    <Box>
      <Text color="green">{'> '}</Text>
      <Text>{value}</Text>
      {hint && <Text color="gray" dimColor>{hint}</Text>}
    </Box>
  );
}

function getHint(input: string): string {
  if (!input.startsWith('/')) return '';
  const match = SLASH_COMMANDS.find(c => c.startsWith(input) && c !== input);
  return match ? match.slice(input.length) : '';
}
```

**Step 5: Run StreamingLine tests to verify they pass**

```bash
cd frontend && pnpm test cli/__tests__/components/StreamingLine.test.tsx
```

Expected: PASS (2 tests)

**Step 6: Commit**

```bash
git add frontend/cli/components/StreamingLine.tsx frontend/cli/components/Prompt.tsx \
  frontend/cli/__tests__/components/StreamingLine.test.tsx
git commit -m "feat(cli): add StreamingLine and Prompt Ink components"
```

---

## Phase 5 — Hooks

### Task 8: `useSlashCommands` hook

**Files:**

- Create: `frontend/cli/hooks/useSlashCommands.ts`
- Create: `frontend/cli/__tests__/hooks/useSlashCommands.test.ts`

**Step 1: Write failing tests**

```typescript
// frontend/cli/__tests__/hooks/useSlashCommands.test.ts
import { parseSlashCommand } from "../../hooks/useSlashCommands";

test("parses /new", () => {
  expect(parseSlashCommand("/new")).toEqual({ command: "new", args: [] });
});

test("parses /context project <id>", () => {
  expect(parseSlashCommand("/context project proj_123")).toEqual({
    command: "context",
    args: ["project", "proj_123"],
  });
});

test("parses /context clear", () => {
  expect(parseSlashCommand("/context clear")).toEqual({
    command: "context",
    args: ["clear"],
  });
});

test("returns null for non-slash input", () => {
  expect(parseSlashCommand("hello")).toBeNull();
});

test("parses /quit", () => {
  expect(parseSlashCommand("/quit")).toEqual({ command: "quit", args: [] });
});
```

**Step 2: Run test to verify it fails**

```bash
cd frontend && pnpm test cli/__tests__/hooks/useSlashCommands.test.ts
```

Expected: FAIL

**Step 3: Implement `useSlashCommands.ts`**

```typescript
export interface ParsedCommand {
  command: string;
  args: string[];
}

export function parseSlashCommand(input: string): ParsedCommand | null {
  if (!input.startsWith("/")) return null;
  const parts = input.slice(1).trim().split(/\s+/);
  return { command: parts[0], args: parts.slice(1) };
}

export type SlashCommandHandler = (parsed: ParsedCommand) => boolean;
```

**Step 4: Run test to verify it passes**

```bash
cd frontend && pnpm test cli/__tests__/hooks/useSlashCommands.test.ts
```

Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add frontend/cli/hooks/useSlashCommands.ts frontend/cli/__tests__/hooks/useSlashCommands.test.ts
git commit -m "feat(cli): add useSlashCommands parser"
```

---

### Task 9: `useStream` hook

**Files:**

- Create: `frontend/cli/hooks/useStream.ts`

> No unit test for this hook — it wraps the live streaming service. Tested via the App integration in Phase 6.

**Implement `useStream.ts`:**

```typescript
import { useCallback, useRef, useState } from "react";
import { getCliAuthHeaders, API_BASE } from "../services/client";
import { loadConfig, saveConfig } from "../auth/store";

export interface ToolCallState {
  id: string;
  tool: string;
  status: "running" | "done" | "error";
  startTime: number;
  durationMs: number | null;
}

export interface StreamState {
  streaming: boolean;
  streamingContent: string;
  toolCalls: ToolCallState[];
  pendingConfirmation: {
    threadId: string;
    details: Record<string, unknown>;
  } | null;
  error: string | null;
}

export function useStream(
  onMessage: (content: string, toolCalls: ToolCallState[]) => void,
) {
  const [state, setState] = useState<StreamState>({
    streaming: false,
    streamingContent: "",
    toolCalls: [],
    pendingConfirmation: null,
    error: null,
  });

  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (message: string, pageContext: Record<string, unknown> = {}) => {
      const config = loadConfig();
      if (!config) throw new Error("Not logged in");

      abortRef.current?.abort();
      const abort = new AbortController();
      abortRef.current = abort;

      const toolCalls: ToolCallState[] = [];
      let content = "";

      setState({
        streaming: true,
        streamingContent: "",
        toolCalls: [],
        pendingConfirmation: null,
        error: null,
      });

      const headers = getCliAuthHeaders();
      const body = JSON.stringify({
        messages: [{ role: "user", content: message }],
        page_context: pageContext,
        thread_id: config.thread_id ?? undefined,
      });

      const res = await fetch(`${API_BASE}/agent/stream`, {
        method: "POST",
        headers,
        body,
        signal: abort.signal,
      });

      if (!res.ok || !res.body) {
        setState((s) => ({
          ...s,
          streaming: false,
          error: `Stream failed: ${res.status}`,
        }));
        return;
      }

      // Update thread_id from trace event
      const updateThread = (threadId: string) => {
        const cfg = loadConfig();
        if (cfg && !cfg.thread_id) saveConfig({ ...cfg, thread_id: threadId });
      };

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let eventType = "";

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventType = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              const raw = line.slice(5).trim();
              try {
                const data = JSON.parse(raw);
                if (eventType === "token") {
                  content += data.content ?? "";
                  setState((s) => ({
                    ...s,
                    streamingContent: content,
                    toolCalls: [...toolCalls],
                  }));
                } else if (eventType === "tool_start") {
                  const tc: ToolCallState = {
                    id: data.tool,
                    tool: data.tool,
                    status: "running",
                    startTime: Date.now(),
                    durationMs: null,
                  };
                  toolCalls.push(tc);
                  setState((s) => ({ ...s, toolCalls: [...toolCalls] }));
                } else if (eventType === "tool_end") {
                  const tc = toolCalls.find((t) => t.tool === data.tool);
                  if (tc) {
                    tc.status = data.is_error ? "error" : "done";
                    tc.durationMs = Date.now() - tc.startTime;
                  }
                  setState((s) => ({ ...s, toolCalls: [...toolCalls] }));
                } else if (eventType === "confirmation") {
                  setState((s) => ({
                    ...s,
                    pendingConfirmation: {
                      threadId: data.thread_id,
                      details: data.confirmation,
                    },
                  }));
                } else if (eventType === "trace") {
                  if (data.thread_id) updateThread(data.thread_id);
                } else if (eventType === "done") {
                  onMessage(content, toolCalls);
                  setState({
                    streaming: false,
                    streamingContent: "",
                    toolCalls: [],
                    pendingConfirmation: null,
                    error: null,
                  });
                } else if (eventType === "error") {
                  setState((s) => ({
                    ...s,
                    streaming: false,
                    error: data.error,
                  }));
                }
              } catch {
                /* skip malformed */
              }
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setState((s) => ({
            ...s,
            streaming: false,
            error: (err as Error).message,
          }));
        }
      } finally {
        reader.releaseLock();
      }
    },
    [onMessage],
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
    setState((s) => ({ ...s, streaming: false, streamingContent: "" }));
  }, []);

  return { state, send, abort };
}
```

**Commit:**

```bash
git add frontend/cli/hooks/useStream.ts
git commit -m "feat(cli): add useStream hook wrapping agent SSE stream"
```

---

## Phase 6 — App & Entry Point

### Task 10: `<App>` root Ink component

**Files:**

- Create: `frontend/cli/components/App.tsx`

```typescript
import { Box, Text, useApp, useInput } from 'ink';
import React, { useCallback, useRef, useState } from 'react';
import { loadConfig, saveConfig } from '../auth/store';
import { ChatMessage } from './ChatMessage';
import { Prompt } from './Prompt';
import { StatusBar } from './StatusBar';
import { StreamingLine } from './StreamingLine';
import { ToolCall } from './ToolCall';
import { useStream } from '../hooks/useStream';
import { parseSlashCommand } from '../hooks/useSlashCommands';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface AppProps {
  initialQuery?: string;
  projectId?: string;
  projectName?: string;
}

export function App({ initialQuery, projectId, projectName }: AppProps) {
  const { exit } = useApp();
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeProject, setActiveProject] = useState<{ id: string; name: string } | undefined>(
    projectId && projectName ? { id: projectId, name: projectName } : undefined
  );

  const config = loadConfig();
  const [threadId, setThreadId] = useState<string | null>(config?.thread_id ?? null);

  const onMessage = useCallback((content: string) => {
    setMessages(prev => [...prev, { role: 'assistant', content }]);
  }, []);

  const { state, send, abort } = useStream(onMessage);

  const pageContext = activeProject
    ? { type: 'project', project_id: activeProject.id, project_name: activeProject.name }
    : { type: 'chat' };

  const handleSubmit = useCallback(async (input: string) => {
    const parsed = parseSlashCommand(input);
    if (parsed) {
      handleSlashCommand(parsed.command, parsed.args);
      return;
    }
    setMessages(prev => [...prev, { role: 'user', content: input }]);
    await send(input, pageContext);
  }, [send, pageContext]);

  const handleSlashCommand = (command: string, args: string[]) => {
    if (command === 'quit') { exit(); return; }
    if (command === 'new') {
      const cfg = loadConfig();
      if (cfg) saveConfig({ ...cfg, thread_id: null });
      setThreadId(null);
      setMessages([]);
      return;
    }
    if (command === 'thread') {
      setMessages(prev => [...prev, { role: 'assistant', content: `Thread: ${threadId ?? 'none'}` }]);
      return;
    }
    if (command === 'context') {
      if (args[0] === 'clear') { setActiveProject(undefined); return; }
      if (args[0] === 'project' && args[1]) {
        setActiveProject({ id: args[1], name: args[2] ?? args[1] });
        return;
      }
    }
    if (command === 'help') {
      setMessages(prev => [...prev, { role: 'assistant', content: '/new /thread /context project <id> /context clear /quit' }]);
      return;
    }
  };

  useInput((_input, key) => {
    if (key.ctrl && _input === 'c') { abort(); exit(); }
  });

  // One-shot mode: send immediately on mount, then exit on done
  const sentInitial = useRef(false);
  React.useEffect(() => {
    if (initialQuery && !sentInitial.current) {
      sentInitial.current = true;
      setMessages([{ role: 'user', content: initialQuery }]);
      send(initialQuery, pageContext).then(() => {
        if (initialQuery) exit();
      });
    }
  }, []);

  return (
    <Box flexDirection="column" height={process.stdout.rows}>
      <StatusBar
        threadId={threadId}
        projectName={activeProject?.name}
        citationCount={0}
      />
      <Box flexDirection="column" flexGrow={1} overflowY="hidden">
        {messages.map((m, i) => (
          <ChatMessage key={i} role={m.role} content={m.content} />
        ))}
        {state.toolCalls.map((tc, i) => (
          <ToolCall key={i} tool={tc.tool} status={tc.status} durationMs={tc.durationMs} />
        ))}
        {state.streamingContent && <StreamingLine content={state.streamingContent} />}
        {state.error && <Text color="red">Error: {state.error}</Text>}
        {state.pendingConfirmation && (
          <Box flexDirection="column" marginY={1}>
            <Text color="yellow">⚠ Agent is requesting confirmation.</Text>
            <Text color="gray">Use /confirm or /deny (not yet implemented — press Ctrl+C to cancel)</Text>
          </Box>
        )}
      </Box>
      {!initialQuery && <Prompt onSubmit={handleSubmit} disabled={state.streaming} />}
    </Box>
  );
}
```

**Commit:**

```bash
git add frontend/cli/components/App.tsx
git commit -m "feat(cli): add App root Ink component (REPL + one-shot)"
```

---

### Task 11: Entry point (`index.ts`)

**Files:**

- Modify: `frontend/cli/index.ts`

**Implement `index.ts`:**

```typescript
#!/usr/bin/env tsx
import { render } from "ink";
import React from "react";
import { login, isTokenExpired } from "./auth/deviceFlow";
import { loadConfig } from "./auth/store";
import { App } from "./components/App";

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  // Handle: ./nous login
  if (command === "login") {
    await login();
    process.exit(0);
  }

  // Guard: must be logged in for everything else
  const config = loadConfig();
  if (!config) {
    console.error("Not logged in. Run: ./nous login");
    process.exit(1);
  }
  if (isTokenExpired(config.expires_at)) {
    console.error("Session expired. Run: ./nous login");
    process.exit(1);
  }

  // One-shot mode: ./nous "some query"
  const initialQuery = args.length > 0 ? args.join(" ") : undefined;

  // REPL mode: ./nous (no args)
  render(React.createElement(App, { initialQuery }));
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
```

**Verify REPL mode works:**

```bash
./nous login     # authenticate first
./nous           # should launch Ink REPL
./nous "hello"   # should stream response and exit
```

**Commit:**

```bash
git add frontend/cli/index.ts
git commit -m "feat(cli): add CLI entry point (login, REPL, one-shot modes)"
```

---

## Phase 7 — Push and Test

### Task 12: Run all CLI tests

```bash
cd frontend && pnpm test cli/
```

Expected: All tests pass. Fix any failures before continuing.

### Task 13: Manual hackathon checklist

Run through each item and confirm:

- [ ] `./nous login` → browser opens at `http://localhost:3000/cli-auth?...`, approve, terminal shows `✓ Logged in as ...`
- [ ] `./nous "hello"` → streams a response and exits cleanly (exit code 0)
- [ ] `./nous` → REPL opens with status bar
- [ ] Type a message → agent responds with streaming text
- [ ] Tool calls appear as `▶ tool_name running…` then `✓ tool_name done (Xs)`
- [ ] `/new` → clears thread
- [ ] `/context project <id>` → status bar shows project name
- [ ] `/quit` or Ctrl+C → exits cleanly

### Task 14: Push

```bash
git push
```

---

## Notes

- `NOUS_API_URL` env var overrides the default `http://localhost:8000/api/v1` — useful for staging
- `NOUS_CONFIG_DIR` env var overrides `~/.nous/` — used in tests
- Token refresh (silent re-auth) is not implemented in v1 — expired sessions require `./nous login` again
- HITL `/confirm` and `/deny` slash commands are stubbed — implement in v2
