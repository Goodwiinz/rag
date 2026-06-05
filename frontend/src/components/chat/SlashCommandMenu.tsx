'use client';

import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import React from 'react';

import type { SlashCommand } from './slashCommands';

export const SLASH_LISTBOX_ID = 'slash-command-listbox';
export const slashOptionId = (id: string): string => `slash-opt-${id}`;

interface SlashCommandMenuProps {
  open: boolean;
  commands: SlashCommand[];
  highlightedIndex: number;
  onHighlight: (index: number) => void;
  /** Run a command (selecting a row or pressing Enter). */
  onRun: (command: SlashCommand) => void;
}

/**
 * Filterable, keyboard-navigable slash-command menu.
 *
 * Rendered as a plain absolutely-positioned listbox that opens *upward* from
 * the composer (inline `bottom: calc(100% + 8px)` on a `relative` wrapper
 * around the input box). That escapes the input box's `overflow-hidden` without
 * a portal and keeps keyboard focus in the textarea.
 *
 * Roving selection: the highlight is tracked here and exposed to assistive tech
 * via `aria-activedescendant` on the textarea (set by the parent), so real DOM
 * focus stays in the input while arrow keys move the highlight.
 */
export function SlashCommandMenu({
  open,
  commands,
  highlightedIndex,
  onHighlight,
  onRun,
}: SlashCommandMenuProps) {
  const reduceMotion = useReducedMotion();

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          role="listbox"
          id={SLASH_LISTBOX_ID}
          aria-label="Slash commands"
          initial={reduceMotion ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 6 }}
          transition={{ duration: 0.16, ease: [0.16, 1, 0.3, 1] }}
          className="absolute left-0 right-0 z-50 overflow-hidden rounded-xl p-1"
          style={{
            // Float 8px above the input box. Inline (not a Tailwind arbitrary
            // value) so the calc() spacing is guaranteed valid CSS.
            bottom: 'calc(100% + 8px)',
            background: 'var(--nous-bg-2)',
            border: '1px solid var(--nous-border-1)',
            boxShadow: 'var(--nous-shadow-lg)',
          }}
        >
          <div
            className="px-3 pt-1.5 pb-1 font-nous-mono text-[9px] uppercase"
            style={{ color: 'var(--nous-fg-3)', letterSpacing: '0.14em' }}
          >
            Slash commands
          </div>
          {commands.map((cmd, index) => {
            const active = index === highlightedIndex;
            return (
              <button
                key={cmd.id}
                id={slashOptionId(cmd.id)}
                role="option"
                aria-selected={active}
                type="button"
                onMouseEnter={() => onHighlight(index)}
                onClick={() => onRun(cmd)}
                className="flex w-full min-h-[44px] items-center gap-3 rounded-lg px-3 text-left transition-colors"
                style={{
                  background: active ? 'var(--nous-aurum)' : 'transparent',
                }}
              >
                <span
                  className="font-nous-mono text-[12px] font-semibold shrink-0"
                  style={{
                    color: active ? 'var(--nous-sol-safe)' : 'var(--nous-fg-1)',
                    letterSpacing: '0.04em',
                  }}
                >
                  {cmd.label}
                </span>
                <span
                  className="font-nous-body text-[12px] truncate"
                  style={{
                    color: active ? 'var(--nous-fg-1)' : 'var(--nous-fg-3)',
                  }}
                >
                  {cmd.title}
                </span>
              </button>
            );
          })}
          {commands.length === 0 && (
            <div
              className="flex min-h-[44px] items-center px-3 font-nous-body text-[12px]"
              style={{ color: 'var(--nous-fg-3)' }}
            >
              No commands match
            </div>
          )}
          <div
            className="hidden sm:flex items-center gap-2 px-3 pt-1 pb-0.5 font-nous-mono text-[9px]"
            style={{ color: 'var(--nous-fg-3)', letterSpacing: '0.08em' }}
          >
            ↑↓ navigate · ↵ run · esc close
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default SlashCommandMenu;
