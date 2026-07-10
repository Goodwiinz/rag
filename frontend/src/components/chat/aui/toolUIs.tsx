'use client';

import { type ReactElement } from 'react';
import { makeAssistantToolUI } from '@assistant-ui/react';
import { FileSearch } from 'lucide-react';

import { HitlApprovalToolUI } from './HitlApprovalToolUI';

/**
 * Declarative per-tool renderers (P2). Each is registered by
 * `toolName` via `makeAssistantToolUI`; a matching tool-call part then routes
 * to it instead of the generic `ToolFallback`. Renderers branch on
 * `status.type` (running → skeleton, incomplete → error, complete → result)
 * and read the structured (backend-redacted) `args` threaded through
 * `ActivityStep.args`.
 *
 * Unregistered tools keep the strong generic `ToolFallback`, so this registry
 * is override-only — add a card here when a tool deserves bespoke rendering.
 */

function resultCount(result: unknown): number | undefined {
  if (result && typeof result === 'object') {
    const r = result as Record<string, unknown>;
    for (const key of ['count', 'total', 'num_results']) {
      if (typeof r[key] === 'number') return r[key] as number;
    }
    for (const key of ['documents', 'results', 'items']) {
      if (Array.isArray(r[key])) return (r[key] as unknown[]).length;
    }
  }
  return undefined;
}

/** Example bespoke card: document search — shows the query and a hit count. */
const SearchDocumentsUI = makeAssistantToolUI<
  { query?: string },
  unknown
>({
  toolName: 'search_documents',
  render: ({ args, status, result }): ReactElement => {
    const query = args?.query;
    const running = status.type === 'running';
    const failed = status.type === 'incomplete';
    const hits = resultCount(result);
    return (
      <div className="my-1.5 flex items-center gap-2 rounded-lg border border-(--nous-border-1) bg-(--nous-bg-2)/60 px-2.5 py-1.5 text-xs text-(--nous-fg-2)">
        <FileSearch
          className="h-3.5 w-3.5 shrink-0 text-(--nous-fg-3)"
          strokeWidth={1.8}
          aria-hidden
        />
        <span className="text-(--nous-fg-3)">Searched documents</span>
        {query ? (
          <span
            className="truncate rounded bg-(--nous-sol-subtle) px-1.5 py-0.5 text-(--nous-fg-accent)"
            style={{ fontFamily: 'var(--nous-font-mono)' }}
          >
            {query}
          </span>
        ) : null}
        <span className="ml-auto shrink-0 text-(--nous-fg-3)">
          {running
            ? 'searching…'
            : failed
              ? 'failed'
              : hits !== undefined
                ? `${hits} ${hits === 1 ? 'result' : 'results'}`
                : 'done'}
        </span>
      </div>
    );
  },
});

/**
 * Mounts every registered tool UI (each renders null — registration is the
 * side effect). Render inside `AssistantRuntimeProvider`. Kept as a single
 * component so `ChatRuntimeProvider` adds one child behind the flag.
 */
export function NousToolUIs(): ReactElement {
  return (
    <>
      <SearchDocumentsUI />
      <HitlApprovalToolUI />
    </>
  );
}
