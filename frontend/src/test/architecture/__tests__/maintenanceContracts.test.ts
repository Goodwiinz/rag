/**
 * Task 6.2 frontend maintenance-contract guards.
 *
 * Static, source-text assertions (no build step) over the chat composition
 * boundaries Tasks 5.2-5.4 established, so a refactor can't quietly regrow
 * the monolith the split undid. Style matches
 * `src/services/__tests__/agentStreamEvents.contract.test.ts`: read real
 * source with `node:fs` and assert on it directly, not a stand-in.
 *
 * Not reimplemented here: "active scripts contain no npm fallback" (the
 * plan's Task 6.2 also names this) already lives in
 * `backend/tests/unit/ci/test_toolchain_contract.py`
 * (`test_root_scripts_do_not_shell_out_to_npm_run` /
 * `test_frontend_scripts_do_not_shell_out_to_npm_run`) — that file is the
 * authoritative JS-toolchain contract test (amendment A8).
 */
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const HERE = dirname(fileURLToPath(import.meta.url));
// frontend/src/test/architecture/__tests__ -> frontend (4 levels up)
const FRONTEND_ROOT = resolve(HERE, '../../../..');

function read(relPath: string): string {
  return readFileSync(resolve(FRONTEND_ROOT, relPath), 'utf-8');
}

function walk(relDir: string, exts = ['.ts', '.tsx']): string[] {
  const abs = resolve(FRONTEND_ROOT, relDir);
  const out: string[] = [];
  for (const entry of readdirSync(abs, { withFileTypes: true })) {
    const rel = `${relDir}/${entry.name}`;
    if (entry.isDirectory()) {
      out.push(...walk(rel, exts));
    } else if (exts.some((ext) => entry.name.endsWith(ext))) {
      out.push(rel);
    }
  }
  return out;
}

describe('chat route stays a composition root', () => {
  const source = read('app/(dashboard)/chat/page.tsx');

  it('imports no API service directly', () => {
    // Persistence/streaming is delegated to the hooks under src/hooks/chat
    // (useChatSession, useChatStreaming, ...) -- the route composes their
    // outputs, it does not call workspaceService/agentChatService itself.
    const serviceImports = [
      // static subpath + barrel imports, and dynamic import() forms
      ...source.matchAll(/from ['"]@\/services(?:\/[^'"]*)?['"]/g),
      ...source.matchAll(/import\(\s*['"]@\/services(?:\/[^'"]*)?['"]\s*\)/g),
    ];
    expect(serviceImports.map((m) => m[0])).toEqual([]);
  });
});

describe('chat-store.ts stays a facade', () => {
  const source = read('src/store/chat-store.ts');
  const lineCount = source.split('\n').length;

  it('stays under the facade line-count ceiling', () => {
    // Measured 158 lines right after Task 5.4's split. ~200 gives headroom
    // for a re-export or a doc comment without permitting the store to
    // regrow business logic that belongs in a slice under src/store/chat/.
    expect(lineCount).toBeLessThanOrEqual(200);
  });

  it('only composes slice creators, it does not define a new one inline', () => {
    const sliceCreatorImports = [
      ...source.matchAll(/from '\.\/chat\/slices\/\w+Slice'/g),
    ];
    expect(sliceCreatorImports.length).toBeGreaterThan(0);
    expect(source).not.toMatch(/function\s+create\w*Slice/);
    expect(source).not.toMatch(/const\s+create\w*Slice\s*=/);
  });
});

describe('presentation components under components/chat', () => {
  it('never import generated OpenAPI types directly when a domain adapter exists', () => {
    // frontend/src/types/api/workspace-contract.ts (+ services/workspaceService.ts)
    // is the domain adapter for workspace/thread/message shapes -- see
    // docs/engineering/api-contracts.md. Presentation components go through
    // it, not through the generated schema module directly.
    const files = walk('src/components/chat');
    // Match real import statements only -- a comment or string mentioning
    // the path must not fail the guard.
    const importPattern =
      /(?:from|import\(?)\s*['"][^'"]*types\/generated\/api['"]/;
    const offenders = files.filter((relPath) => importPattern.test(read(relPath)));
    expect(offenders).toEqual([]);
  });
});
