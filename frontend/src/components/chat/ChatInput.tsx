'use client';

import { cn } from '@/lib/utils';
import { RAGToggle } from './RAGToggle';
import { motion } from 'framer-motion';
import { ArrowUp, Bot, Mic, Paperclip, Square } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  isLoading: boolean;
  enableRAG: boolean;
  onRAGToggle: (enabled: boolean) => void;
  isRAGLoading?: boolean;
  inputRef?: React.RefObject<HTMLTextAreaElement>;
  onAttach?: (files: FileList) => void;
}

export function ChatInput({
  value,
  onChange,
  onSubmit,
  onStop,
  isLoading,
  enableRAG,
  onRAGToggle,
  isRAGLoading,
  inputRef,
  onAttach,
}: ChatInputProps) {
  const internalRef = useRef<HTMLTextAreaElement>(null);
  const textareaRef = inputRef ?? internalRef;
  const [isFocused, setIsFocused] = useState(false);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && value.trim()) {
        onSubmit();
      }
    }
  };

  const isDisabled = isLoading;
  const charCount = value.length;
  const maxChars = 4000;
  const isNearLimit = charCount > maxChars * 0.8;

  return (
    <div className="z-40 bg-[var(--terminal-bg)] pt-2 pb-4 px-4 border-t border-[var(--terminal-border)]">
      <div className="max-w-4xl mx-auto">
        <motion.div
          className={cn(
            'relative rounded-lg overflow-visible transition-all duration-300',
            'bg-[var(--terminal-surface)] border border-[var(--terminal-border)]',
            isFocused &&
              'border-[var(--phosphor-green)]/30 ring-1 ring-[var(--phosphor-green)]/10 shadow-[0_0_15px_-5px_rgba(212,160,57,0.1)]'
          )}
        >
          {/* Top Bar: Agent Label, RAG Toggle & Status */}
          <div className="flex items-center justify-between px-4 py-1.5 bg-[var(--terminal-elevated)]/50 border-b border-[var(--terminal-border)] rounded-t-xl">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border bg-[var(--terminal-surface)] border-[var(--terminal-border)]">
                <Bot className="w-3.5 h-3.5 text-[var(--phosphor-green)]" />
                <span
                  className="text-[var(--terminal-text)] text-xs"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  NOUS AGENT
                </span>
                <span className="px-1 py-0.5 rounded bg-[var(--phosphor-green)]/20 text-[var(--phosphor-green)] text-[8px] uppercase">
                  Agent
                </span>
              </div>
              <RAGToggle
                enabled={enableRAG}
                onToggle={onRAGToggle}
                isLoading={isRAGLoading}
                disabled={isLoading}
              />
            </div>
            <div className="flex items-center gap-3">
              {/* RAG loading indicator */}
              {isRAGLoading && (
                <span
                  className="text-[9px] text-[var(--phosphor-green)] animate-pulse"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  RETRIEVING...
                </span>
              )}
              <span
                className={cn(
                  'text-[9px] transition-colors',
                  isNearLimit
                    ? 'text-[var(--amber-gold)]'
                    : 'text-[var(--terminal-text-dim)]'
                )}
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                {charCount}/{maxChars}
              </span>
            </div>
          </div>

          <div className="p-3 sm:p-4">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              placeholder="Inject query into neural stream..."
              rows={1}
              className="w-full bg-transparent text-[var(--terminal-text)] text-sm resize-none outline-none placeholder:text-[var(--terminal-text-dim)]/50 selection:bg-[var(--phosphor-green)]/20 selection:text-[var(--phosphor-green)]"
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                minHeight: '44px',
                maxHeight: '200px',
              }}
              disabled={isDisabled}
            />

            <div className="flex items-center justify-between mt-2">
              <div className="flex items-center gap-1">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <label
                        className="p-2 rounded-lg hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] transition-colors group cursor-pointer inline-flex"
                        aria-label="Attach artifact"
                      >
                        <Paperclip className="w-4 h-4 group-hover:text-[var(--phosphor-green)] transition-colors" />
                        <input
                          type="file"
                          multiple
                          className="hidden"
                          onChange={(e) => {
                            const files = e.target.files;
                            if (files && files.length > 0 && onAttach) {
                              onAttach(files);
                            }
                            e.target.value = '';
                          }}
                        />
                      </label>
                    </TooltipTrigger>
                    <TooltipContent>Attach artifact</TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        className="p-2 rounded-lg hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] transition-colors group"
                        aria-label="Voice input"
                      >
                        <Mic className="w-4 h-4 group-hover:text-[var(--phosphor-green)] transition-colors" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>Voice input</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>

              {isLoading ? (
                <button
                  onClick={onStop}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--error-red)]/10 border border-[var(--error-red)]/50 text-[var(--error-red)] text-[10px] font-bold hover:bg-[var(--error-red)]/20 transition-all shadow-[0_0_10px_rgba(239,68,68,0.05)]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <Square className="w-3 h-3" />
                  HALT
                </button>
              ) : (
                <button
                  onClick={onSubmit}
                  disabled={!value.trim() || isDisabled}
                  title="Send message (Enter)"
                  className={cn(
                    'flex items-center gap-2 px-6 py-2 rounded text-[10px] font-bold tracking-widest transition-all duration-300',
                    value.trim() && !isDisabled
                      ? 'bg-[var(--phosphor-green)] text-[#0A0A0A] hover:bg-[var(--phosphor-green)]/90 hover:shadow-[0_0_15px_rgba(212,160,57,0.3)] active:scale-95'
                      : 'bg-transparent text-[var(--terminal-text-dim)] border border-[var(--terminal-border)] cursor-not-allowed'
                  )}
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  TRANSMIT
                  <ArrowUp className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        </motion.div>

        {/* Keyboard Hint */}
        <motion.div
          initial={{ opacity: 0.5 }}
          animate={{ opacity: isFocused ? 0.3 : 0.5 }}
          className="flex items-center justify-center gap-4 mt-2 text-[9px] text-[var(--terminal-text-dim)] uppercase tracking-tighter"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          <span>[Enter] Send</span>
          <span>[Shift+Enter] Line Break</span>
          <span className="hidden sm:inline">[/] Commands</span>
        </motion.div>
      </div>
    </div>
  );
}

export default ChatInput;
