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
    <div className="z-40 pt-2 pb-[72px] md:pb-4 px-2 sm:px-4 safe-area-bottom">
      <div className="max-w-4xl mx-auto">
        <motion.div
          className={cn(
            'nous-glass nous-composer-glow relative rounded-2xl overflow-visible',
            isFocused && 'nous-composer-glow'
          )}
          animate={isFocused ? { y: -2 } : { y: 0 }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
        >
          {/* Toolbar row */}
          <div className="flex items-center justify-between px-3 sm:px-4 py-2 border-b border-[var(--nous-border-1)] gap-2 overflow-x-auto">
            <div className="flex items-center gap-2 sm:gap-3 min-w-0">
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--nous-sol)]/10 border border-[var(--nous-sol)]/20 shrink-0">
                <Bot className="w-3.5 h-3.5 text-[var(--nous-sol)]" />
                <span
                  className="text-[var(--nous-fg-1)] text-[11px] font-medium hidden sm:inline"
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
                >
                  NOUS
                </span>
              </div>
              <RAGToggle
                enabled={enableRAG}
                onToggle={onRAGToggle}
                isLoading={isRAGLoading}
                disabled={isLoading}
              />
              {onModelChange && (
                <div className="hidden sm:block">
                  <ModelSelector
                    models={AVAILABLE_MODELS}
                    selectedModelId={selectedModelId}
                    onModelChange={onModelChange}
                  />
                </div>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {isRAGLoading && (
                <span
                  className="text-[9px] text-[var(--nous-sol)] animate-pulse hidden sm:inline"
                  style={{ fontFamily: 'var(--nous-font-mono)' }}
                >
                  RETRIEVING
                </span>
              )}
              <span
                className={cn(
                  'text-[9px] transition-colors whitespace-nowrap',
                  isNearLimit
                    ? 'text-[var(--nous-corona)]'
                    : 'text-[var(--nous-fg-3)]'
                )}
                style={{ fontFamily: 'var(--nous-font-mono)' }}
              >
                {charCount}/{maxChars}
              </span>
            </div>
          </div>

          {/* Textarea */}
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
              className="w-full bg-transparent text-[var(--nous-fg-1)] text-[15px] sm:text-base resize-none outline-none placeholder:text-[var(--nous-fg-3)]/60 selection:bg-[var(--nous-sol)]/20"
              style={{
                fontFamily: 'var(--nous-font-body)',
                lineHeight: '1.6',
                minHeight: '44px',
                maxHeight: '200px',
              }}
              disabled={isDisabled}
            />

            {/* Action row */}
            <div className="flex items-center justify-between mt-2 pt-1">
              <div className="flex items-center gap-0.5">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <label
                        className="p-2.5 sm:p-2 rounded-xl hover:bg-[var(--nous-sol)]/8 text-[var(--nous-fg-3)] hover:text-[var(--nous-fg-1)] transition-colors group cursor-pointer inline-flex"
                        aria-label="Attach artifact"
                      >
                        <Paperclip className="w-5 h-5 sm:w-[18px] sm:h-[18px] group-hover:text-[var(--nous-sol)] transition-colors" />
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
                          'p-2.5 sm:p-2 rounded-xl transition-colors group',
                          voiceSupported
                            ? 'hover:bg-[var(--nous-sol)]/8 text-[var(--nous-fg-3)] hover:text-[var(--nous-fg-1)]'
                            : 'text-[var(--nous-fg-3)]/40 cursor-not-allowed',
                          isListening &&
                            'bg-[var(--nous-sol)]/10 text-[var(--nous-sol)]'
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
                            'w-5 h-5 sm:w-[18px] sm:h-[18px] transition-colors',
                            isListening
                              ? 'text-[var(--nous-sol)] animate-pulse'
                              : 'group-hover:text-[var(--nous-sol)]'
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
                  className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-[var(--nous-mars)]/10 border border-[var(--nous-mars)]/40 text-[var(--nous-mars)] text-[11px] font-semibold hover:bg-[var(--nous-mars)]/20 transition-all h-10 sm:h-9"
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
                >
                  <Square className="w-3 h-3" />
                  Stop
                </button>
              ) : (
                <button
                  onClick={onSubmit}
                  disabled={!value.trim() || isDisabled}
                  title="Send message (Enter)"
                  className="nous-send-pill flex items-center justify-center gap-1.5 h-10 w-10 sm:h-9 sm:w-auto sm:px-5 text-[12px]"
                >
                  <ArrowUp className="w-4 h-4 sm:w-3.5 sm:h-3.5" />
                  <span className="hidden sm:inline">Send</span>
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
