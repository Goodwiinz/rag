'use client';

import { cn } from '@/lib/utils';
import { AVAILABLE_MODELS, ModelSelector } from './ModelSelector';
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
  selectedModelId?: string;
  onModelChange?: (id: string) => void;
}

type SpeechRecognitionEventLike = {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
};
type SpeechRecognitionInstance = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type SpeechRecognitionCtor = new () => SpeechRecognitionInstance;

function getSpeechRecognition(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
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
  selectedModelId,
  onModelChange,
}: ChatInputProps) {
  const internalRef = useRef<HTMLTextAreaElement>(null);
  const textareaRef = inputRef ?? internalRef;
  const [isFocused, setIsFocused] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  // Defer the Web Speech API feature check to after mount. Running it during
  // render produces an SSR/client mismatch (server: window is undefined →
  // false; client: browser supports it → true). Start `false`, flip after
  // hydration so the first server and client renders match.
  const [voiceSupported, setVoiceSupported] = useState(false);
  useEffect(() => {
    setVoiceSupported(getSpeechRecognition() !== null);
  }, []);

  const toggleVoice = (): void => {
    const Ctor = getSpeechRecognition();
    if (!Ctor) return;
    if (isListening) {
      recognitionRef.current?.stop();
      return;
    }
    const recognition = new Ctor();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';
    recognition.onresult = (event) => {
      const transcript = event.results[0]?.[0]?.transcript ?? '';
      if (transcript) {
        onChange(value ? `${value} ${transcript}` : transcript);
      }
    };
    recognition.onend = () => {
      setIsListening(false);
      recognitionRef.current = null;
    };
    recognition.onerror = () => {
      setIsListening(false);
      recognitionRef.current = null;
    };
    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  };

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

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
              {onModelChange && (
                <ModelSelector
                  models={AVAILABLE_MODELS}
                  selectedModelId={selectedModelId}
                  onModelChange={onModelChange}
                />
              )}
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
              placeholder="Message NOUS…"
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
                        type="button"
                        onClick={toggleVoice}
                        disabled={!voiceSupported}
                        aria-pressed={isListening}
                        className={cn(
                          'p-2 rounded-lg transition-colors group',
                          voiceSupported
                            ? 'hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)]'
                            : 'text-[var(--terminal-text-dim)]/40 cursor-not-allowed',
                          isListening &&
                            'bg-[var(--phosphor-green)]/10 text-[var(--phosphor-green)]'
                        )}
                        aria-label={
                          !voiceSupported
                            ? 'Voice input not supported'
                            : isListening
                              ? 'Stop voice input'
                              : 'Voice input'
                        }
                      >
                        <Mic
                          className={cn(
                            'w-4 h-4 transition-colors',
                            isListening
                              ? 'text-[var(--phosphor-green)] animate-pulse'
                              : 'group-hover:text-[var(--phosphor-green)]'
                          )}
                        />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>
                      {!voiceSupported
                        ? 'Voice input not supported'
                        : isListening
                          ? 'Stop voice input'
                          : 'Voice input'}
                    </TooltipContent>
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
      </div>
    </div>
  );
}

export default ChatInput;
