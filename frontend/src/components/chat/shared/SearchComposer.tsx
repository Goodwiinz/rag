'use client';

import { cn } from '@/lib/utils';
import { ArrowUp, Square } from 'lucide-react';
import { useEffect, useRef } from 'react';

export interface SearchComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  isLoading: boolean;
  isDisabled?: boolean;
  placeholder?: string;
  textareaRef?: React.RefObject<HTMLTextAreaElement>;
}

export function SearchComposer({
  value,
  onChange,
  onSubmit,
  onStop,
  isLoading,
  isDisabled = false,
  placeholder = 'Message NOUS…',
  textareaRef,
}: SearchComposerProps) {
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
    <div className="z-40 bg-gradient-to-t from-[var(--nous-bg-1)] via-[var(--nous-bg-1)] to-transparent px-4 pb-[72px] md:pb-4 pt-4">
      <div className="mx-auto max-w-5xl 2xl:max-w-6xl">
        <div
          className={cn(
            'nous-glass nous-composer-glow overflow-visible rounded-xl border border-[var(--nous-border-1)] shadow-2xl shadow-black/50'
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
              className="w-full resize-none bg-transparent text-sm text-[var(--nous-fg-1)] outline-none placeholder:text-[var(--nous-fg-3)]/50 selection:bg-[var(--nous-sol)]/20 selection:text-[var(--nous-sol)]"
              style={{
                fontFamily: 'var(--nous-font-body)',
                minHeight: '44px',
                maxHeight: '200px',
              }}
              disabled={isDisabled}
            />

            <div className="mt-2 flex items-center justify-end">
              {isLoading ? (
                <button
                  onClick={onStop}
                  aria-label="Stop generation"
                  title="Stop generation"
                  className="flex items-center gap-2 rounded-lg border border-red-500/50 bg-red-500/10 px-4 py-2 text-xs font-medium text-red-400 transition-all hover:bg-red-500/20"
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
                >
                  <Square className="h-3 w-3" />
                  Stop
                </button>
              ) : (
                <button
                  onClick={onSubmit}
                  disabled={!value.trim() || isDisabled}
                  title="Send message (Enter)"
                  aria-label="Send message"
                  className={cn(
                    'nous-send-pill flex items-center gap-2 rounded-full h-10 w-10 sm:h-9 sm:w-auto sm:px-5 justify-center text-xs font-semibold tracking-wide transition-all duration-300',
                    value.trim() && !isDisabled
                      ? 'bg-[var(--nous-sol)] text-[var(--nous-erebus)] shadow-[0_0_18px_rgba(212,160,57,0.25)] hover:scale-[1.02] hover:shadow-[0_0_24px_rgba(212,160,57,0.35)] active:scale-95'
                      : 'cursor-not-allowed border border-[var(--nous-border-1)] bg-[var(--nous-bg-3)] text-[var(--nous-fg-3)]/80'
                  )}
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
                >
                  <span className="hidden sm:inline">Send</span>
                  <ArrowUp className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        </div>

        <div
          className="mt-2 flex items-center justify-center gap-4 text-[9px] uppercase tracking-tighter text-[var(--nous-fg-3)]"
          style={{ fontFamily: 'var(--nous-font-mono)' }}
        >
          <span>[Enter] Send</span>
          <span>[Shift+Enter] Line Break</span>
          <span className="hidden sm:inline">[/] Commands</span>
        </div>
      </div>
    </div>
  );
}

export default SearchComposer;
