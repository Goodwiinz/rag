'use client';

import { cn } from '@/lib/utils';
import { ArrowUp, Square } from 'lucide-react';
import { useEffect, useRef } from 'react';

export interface TerminalChatComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  isLoading: boolean;
  isDisabled?: boolean;
  placeholder?: string;
  textareaRef?: React.RefObject<HTMLTextAreaElement>;
}

export function TerminalChatComposer({
  value,
  onChange,
  onSubmit,
  onStop,
  isLoading,
  isDisabled = false,
  placeholder = 'Message NOUS…',
  textareaRef,
}: TerminalChatComposerProps) {
  const internalRef = useRef<HTMLTextAreaElement>(null);
  const composerRef = textareaRef ?? internalRef;

  useEffect(() => {
    if (!composerRef.current) {
      return;
    }

    composerRef.current.style.height = 'auto';
    composerRef.current.style.height = `${Math.min(
      composerRef.current.scrollHeight,
      200
    )}px`;
  }, [value, composerRef]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && !isDisabled && value.trim()) {
        onSubmit();
      }
    }
  };

  return (
    <div className="z-40 bg-gradient-to-t from-[var(--terminal-bg)] via-[var(--terminal-bg)] to-transparent px-4 pb-4 pt-4">
      <div className="mx-auto max-w-5xl 2xl:max-w-6xl">
        <div
          className={cn(
            'overflow-visible rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-2xl shadow-black/50 ring-1 ring-[var(--terminal-border)]/30'
          )}
        >
          <div className="p-3 sm:p-4">
            <textarea
              ref={composerRef}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              rows={1}
              className="w-full resize-none bg-transparent text-sm text-[var(--terminal-text)] outline-none placeholder:text-[var(--terminal-text-dim)]/50 selection:bg-[var(--phosphor-green)]/20 selection:text-[var(--phosphor-green)]"
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                minHeight: '44px',
                maxHeight: '200px',
              }}
              disabled={isDisabled}
            />

            <div className="mt-2 flex items-center justify-end">
              {isLoading ? (
                <button
                  onClick={onStop}
                  className="flex items-center gap-2 rounded-lg border border-[var(--error-red)]/50 bg-[var(--error-red)]/10 px-4 py-2 text-[10px] font-bold text-[var(--error-red)] transition-all hover:bg-[var(--error-red)]/20"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <Square className="h-3 w-3" />
                  HALT
                </button>
              ) : (
                <button
                  onClick={onSubmit}
                  disabled={!value.trim() || isDisabled}
                  title="Send message (Enter)"
                  className={cn(
                    'flex items-center gap-2 rounded-lg px-5 py-2 text-[10px] font-bold tracking-widest transition-all duration-300',
                    value.trim() && !isDisabled
                      ? 'bg-[var(--phosphor-green)] text-[var(--terminal-bg)] shadow-[0_0_18px_rgba(212,160,57,0.25)] hover:scale-[1.02] hover:shadow-[0_0_24px_rgba(212,160,57,0.35)] active:scale-95'
                      : 'cursor-not-allowed border border-[var(--terminal-border)] bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)]/80'
                  )}
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  TRANSMIT
                  <ArrowUp className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>
        </div>

        <div
          className="mt-2 flex items-center justify-center gap-4 text-[9px] uppercase tracking-tighter text-[var(--terminal-text-dim)]"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          <span>[Enter] Send</span>
          <span>[Shift+Enter] Line Break</span>
          <span className="hidden sm:inline">[/] Commands</span>
        </div>
      </div>
    </div>
  );
}

export default TerminalChatComposer;
