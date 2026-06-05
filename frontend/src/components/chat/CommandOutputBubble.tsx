'use client';

import { Loader2 } from 'lucide-react';

import type { CommandAction, CommandOutput } from './commandOutput';

interface CommandOutputBubbleProps {
  output: CommandOutput;
  onItemAction: (action: CommandAction) => void;
}

/**
 * Terminal-style rendering of a slash-command result inside the chat
 * transcript. Shows the echoed command, then either monospace `lines` or
 * clickable `items` (tap to switch thread / set project context / cite a
 * paper). All NOUS tokens, monospace, on-brand with the streaming pill.
 */
export function CommandOutputBubble({
  output,
  onItemAction,
}: CommandOutputBubbleProps) {
  const { command, status, lines, items, emptyText, note } = output;

  return (
    <div className="my-3" role="group" aria-label={`Result of ${command}`}>
      <div
        className="rounded-xl px-3.5 py-3 font-nous-mono"
        style={{
          background: 'var(--nous-bg-2)',
          border: '1px solid var(--nous-border-1)',
        }}
      >
        {/* Echoed command line */}
        <div className="flex items-center gap-2 text-[12px]">
          <span style={{ color: 'var(--nous-sol)' }}>&rsaquo;</span>
          <span
            className="font-semibold"
            style={{ color: 'var(--nous-fg-2)', letterSpacing: '0.02em' }}
          >
            {command}
          </span>
          {status === 'loading' && (
            <Loader2
              className="h-3 w-3 animate-spin"
              style={{ color: 'var(--nous-fg-3)' }}
            />
          )}
        </div>

        {/* Monospace lines */}
        {lines && lines.length > 0 && (
          <div className="mt-2 space-y-0.5">
            {lines.map((line, i) => (
              <div
                key={i}
                className="whitespace-pre text-[12px] leading-relaxed"
                style={{ color: 'var(--nous-fg-2)' }}
              >
                {line}
              </div>
            ))}
          </div>
        )}

        {/* Clickable items */}
        {items && items.length > 0 && (
          <div className="mt-2 space-y-0.5">
            {items.map((item) => {
              const interactive = !!item.action;
              const Tag = interactive ? 'button' : 'div';
              return (
                <Tag
                  key={item.key}
                  {...(interactive
                    ? {
                        type: 'button' as const,
                        onClick: () => item.action && onItemAction(item.action),
                      }
                    : {})}
                  className={
                    'flex w-full min-h-[40px] items-center gap-2.5 rounded-md px-2 text-left transition-colors' +
                    (interactive
                      ? ' cursor-pointer hover:bg-[var(--nous-aurum)] dark:hover:bg-[var(--nous-ember)]'
                      : '')
                  }
                >
                  <span
                    className="w-3 shrink-0 text-center text-[12px]"
                    style={{
                      color: item.active
                        ? 'var(--nous-sol)'
                        : 'var(--nous-fg-3)',
                    }}
                    aria-hidden
                  >
                    {item.active ? '▸' : '·'}
                  </span>
                  <span
                    className="flex-1 truncate text-[12px]"
                    style={{
                      color: 'var(--nous-fg-1)',
                      fontWeight: item.active ? 600 : 400,
                    }}
                  >
                    {item.label}
                  </span>
                  {item.meta && (
                    <span
                      className="shrink-0 text-[11px] tabular-nums"
                      style={{ color: 'var(--nous-fg-3)' }}
                    >
                      {item.meta}
                    </span>
                  )}
                </Tag>
              );
            })}
          </div>
        )}

        {/* Empty state */}
        {items && items.length === 0 && status !== 'loading' && (
          <div
            className="mt-2 text-[12px]"
            style={{ color: 'var(--nous-fg-3)' }}
          >
            {emptyText || 'Nothing to show.'}
          </div>
        )}

        {/* Footer hint */}
        {note && (
          <div
            className="mt-2 text-[11px]"
            style={{ color: 'var(--nous-fg-3)' }}
          >
            {note}
          </div>
        )}
      </div>
    </div>
  );
}

export default CommandOutputBubble;
