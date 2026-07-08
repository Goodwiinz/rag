'use client';

import { Fragment, useEffect, useRef, type ReactElement } from 'react';
import { makeAssistantToolUI } from '@assistant-ui/react';
import { ShieldCheck } from 'lucide-react';

import { HITL_APPROVAL_TOOL, useHitlBridge } from './hitlBridge';

export { HITL_APPROVAL_TOOL };

function formatArgValue(value: unknown, max = 140): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string') {
    return value.length > max ? value.slice(0, max - 1) + '…' : value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  try {
    const s = JSON.stringify(value);
    return s.length > max ? s.slice(0, max - 1) + '…' : s;
  } catch {
    return '[unserializable]';
  }
}

/**
 * Renders the HITL approval gate in-band at the tool-call position (replaces
 * the detached page-level banner under AUI_FULL). NOUS resolves confirmations
 * over the separate streamConfirm endpoint, so approve/deny drive the hardened
 * `handleConfirmation` via the bridge store — `respondToApproval` is called
 * best-effort for runtime part-state, but the bridge is the source of truth.
 * Accessibility (alertdialog role, Approve autofocus, Escape=deny, disabled
 * while responding) mirrors the banner it replaces.
 */
export const HitlApprovalToolUI = makeAssistantToolUI<
  { toolName?: string; toolArgs?: Record<string, unknown> },
  unknown
>({
  toolName: HITL_APPROVAL_TOOL,
  display: 'standalone',
  render: ({ args, respondToApproval }): ReactElement | null => {
    const request = useHitlBridge((s) => s.request);
    const respond = useHitlBridge((s) => s.respond);
    const isResponding = useHitlBridge((s) => s.isResponding);
    const approveRef = useRef<HTMLButtonElement>(null);

    // Move focus to Approve when the gate appears (mirrors the banner).
    useEffect(() => {
      if (request) approveRef.current?.focus();
    }, [request]);

    // Gate already resolved (bridge closed) — render nothing.
    if (!request || !respond) return null;

    const toolName = args?.toolName ?? request.toolName ?? 'this action';
    const toolArgs = args?.toolArgs ?? request.args ?? {};
    const argEntries = Object.entries(toolArgs);

    const decide = (approved: boolean) => {
      // Best-effort runtime signal; the bridge does the real resolution.
      try {
        respondToApproval?.({ approved });
      } catch {
        /* respondToApproval is not wired for the external-store transport */
      }
      respond(approved);
    };

    return (
      <div
        role="alertdialog"
        aria-label="Approval needed"
        aria-describedby="hitl-tool-desc"
        tabIndex={-1}
        onKeyDown={(e) => {
          if (e.key === 'Escape' && !isResponding) decide(false);
        }}
        className="my-2 rounded-xl border border-(--nous-sol)/30 bg-(--nous-sol)/5 p-3 outline-hidden sm:p-4"
      >
        <div className="mb-2 flex items-center gap-2">
          <ShieldCheck
            aria-hidden
            className="h-4 w-4 text-(--nous-sol)"
            strokeWidth={1.8}
          />
          <p
            className="text-sm font-medium text-(--nous-fg-2)"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            Approval needed
          </p>
        </div>
        <p
          id="hitl-tool-desc"
          className="mb-3 text-sm leading-relaxed text-(--nous-fg-1)"
          style={{ fontFamily: 'var(--nous-font-ui)' }}
        >
          The agent wants to run{' '}
          <span
            className="rounded bg-(--nous-sol-subtle) px-1.5 py-0.5 text-(--nous-fg-accent)"
            style={{ fontFamily: 'var(--nous-font-mono)' }}
          >
            {toolName}
          </span>
          . Approve to let it continue, or Deny to stop.
        </p>
        {argEntries.length > 0 && (
          <dl
            className="mb-3 grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-1.5 rounded-lg border border-(--nous-border-1) bg-(--nous-bg-2)/60 p-3 text-xs"
            aria-label="Tool arguments"
          >
            {argEntries.map(([key, value]) => (
              <Fragment key={key}>
                <dt
                  className="whitespace-nowrap text-(--nous-fg-3)"
                  style={{ fontFamily: 'var(--nous-font-mono)' }}
                >
                  {key}
                </dt>
                <dd
                  className="break-all text-(--nous-fg-2)"
                  style={{ fontFamily: 'var(--nous-font-mono)' }}
                >
                  {formatArgValue(value)}
                </dd>
              </Fragment>
            ))}
          </dl>
        )}
        <div className="flex items-center gap-3">
          <button
            ref={approveRef}
            onClick={() => decide(true)}
            disabled={isResponding}
            className="rounded-xl bg-(--nous-sol) px-4 py-2 text-xs font-semibold text-(--nous-erebus) transition-all hover:brightness-110 disabled:opacity-50"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            {isResponding ? 'Processing…' : 'Approve'}
          </button>
          <button
            onClick={() => decide(false)}
            disabled={isResponding}
            className="rounded-xl border border-(--nous-mars)/40 bg-(--nous-mars)/5 px-4 py-2 text-xs font-semibold text-(--nous-mars) transition-all hover:bg-(--nous-mars)/10 disabled:opacity-50"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            Deny
          </button>
        </div>
      </div>
    );
  },
});
