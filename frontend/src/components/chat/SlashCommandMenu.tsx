'use client';

import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import React from 'react';

import { ProjectPickerPopover } from '@/components/context-rail/ProjectPickerPopover';

import type { SlashCommand } from './slashCommands';

export const SLASH_LISTBOX_ID = 'slash-command-listbox';
export const slashOptionId = (id: string): string => `slash-opt-${id}`;

interface SlashCommandMenuProps {
  open: boolean;
  commands: SlashCommand[];
  highlightedIndex: number;
  onHighlight: (index: number) => void;
  /** Run an `action` command (selecting a row or pressing Enter). */
  onRun: (command: SlashCommand) => void;
  /** Active thread + workspace for the `/projects` picker. */
  threadId?: string;
  workspaceId?: string;
  /** Called when a project is chosen via the `/projects` picker. */
  onSetProjectContext?: (projectId: string, projectName: string) => void;
  /**
   * Ref to the `/projects` row button, so a keyboard Enter on that row can
   * synthesise a click and open the (mouse-driven) picker.
   */
  projectsTriggerRef?: React.RefObject<HTMLButtonElement>;
}

/**
 * Filterable, keyboard-navigable slash-command menu.
 *
 * Rendered as a plain absolutely-positioned listbox that opens *upward* from
 * the composer (`bottom: 100% + 8px` of a `relative` wrapper around the input
 * box). That escapes the input box's `overflow-hidden` without a portal, keeps
 * keyboard focus in the textarea (rows never steal it), and lets `/projects`
 * reuse `ProjectPickerPopover` as a single, non-nested Radix popover.
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
  threadId,
  workspaceId,
  onSetProjectContext,
  projectsTriggerRef,
}: SlashCommandMenuProps) {
  const reduceMotion = useReducedMotion();

  const renderRow = (cmd: SlashCommand, index: number) => {
    const active = index === highlightedIndex;
    const rowClass =
      'flex w-full min-h-[44px] items-center gap-3 rounded-lg px-3 text-left transition-colors';
    const rowStyle: React.CSSProperties = {
      background: active ? 'var(--nous-aurum)' : 'transparent',
    };
    const labelColor = active ? 'var(--nous-sol-safe)' : 'var(--nous-fg-1)';
    const titleColor = active ? 'var(--nous-sol-safe)' : 'var(--nous-fg-3)';

    const inner = (
      <>
        <span
          className="font-nous-mono text-[12px] font-semibold shrink-0"
          style={{ color: labelColor, letterSpacing: '0.04em' }}
        >
          {cmd.label}
        </span>
        <span
          className="font-nous-body text-[12px] truncate"
          style={{ color: titleColor }}
        >
          {cmd.title}
        </span>
      </>
    );

    const shared = {
      id: slashOptionId(cmd.id),
      role: 'option' as const,
      'aria-selected': active,
      onMouseEnter: () => onHighlight(index),
    };

    // `/projects` row IS the trigger of ProjectPickerPopover (a self-contained
    // Radix popover). Mouse click opens it; keyboard Enter clicks it via ref.
    if (cmd.kind === 'picker' && cmd.id === 'projects') {
      return (
        <ProjectPickerPopover
          key={cmd.id}
          threadId={threadId ?? ''}
          workspaceId={workspaceId}
          onProjectBound={(id, name) => onSetProjectContext?.(id, name)}
        >
          <button
            {...shared}
            ref={projectsTriggerRef}
            type="button"
            className={rowClass}
            style={rowStyle}
          >
            {inner}
          </button>
        </ProjectPickerPopover>
      );
    }

    return (
      <button
        {...shared}
        key={cmd.id}
        type="button"
        className={rowClass}
        style={rowStyle}
        onClick={() => onRun(cmd)}
      >
        {inner}
      </button>
    );
  };

  return (
    <AnimatePresence>
      {open && commands.length > 0 && (
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
            Commands
          </div>
          {commands.map((cmd, i) => renderRow(cmd, i))}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default SlashCommandMenu;
