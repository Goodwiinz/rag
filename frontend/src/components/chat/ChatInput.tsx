'use client';

import { cn } from '@/lib/utils';
import { AVAILABLE_MODELS, ModelSelector } from './ModelSelector';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Bot,
  Image as ImageIcon,
  Mic,
  Paperclip,
  Square,
} from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';

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
  }, [value, textareaRef]);

  const handleKeyDown = (e: React.KeyboardEvent): void => {
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
  const fillPct = Math.min(100, Math.round((charCount / maxChars) * 100));
  const isNearLimit = charCount > maxChars * 0.8;

  return (
    <div
      className="z-40 px-2 sm:px-6 pt-3 pb-[80px] md:pb-4 border-t"
      style={{
        background: 'var(--nous-bg-1)',
        borderColor: 'var(--nous-border-1)',
      }}
    >
      <div className="max-w-[820px] mx-auto">
        <motion.div
          className="rounded-[14px] overflow-hidden"
          style={{
            background: 'var(--nous-bg-2)',
            border: `1px solid ${
              isFocused ? 'rgba(212, 160, 57, 0.4)' : 'var(--nous-border-1)'
            }`,
            boxShadow: isFocused
              ? '0 0 0 3px rgba(212, 160, 57, 0.10), 0 8px 24px rgba(10,10,14,0.06)'
              : '0 1px 2px rgba(10,10,14,0.04)',
            transition:
              'border-color 260ms var(--nous-ease-out), box-shadow 260ms var(--nous-ease-out)',
          }}
          animate={isFocused ? { y: -1 } : { y: 0 }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
        >
          {/* Top strip — agent badge, RAG toggle, model, counter */}
          <div
            className="flex items-center justify-between gap-2 px-3 py-2 border-b overflow-x-auto"
            style={{
              background: 'var(--nous-bg-1)',
              borderColor: 'var(--nous-border-1)',
            }}
          >
            <div className="flex items-center gap-2 min-w-0">
              <div
                className="inline-flex items-center gap-[7px] rounded-md shrink-0"
                style={{
                  padding: '4px 9px 4px 7px',
                  background: 'var(--nous-bg-2)',
                  border: '1px solid var(--nous-border-1)',
                }}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{
                    background: 'var(--nous-terra)',
                    boxShadow: '0 0 0 2px rgba(52, 211, 153, 0.15)',
                    animation: 'nous-pulse 2s ease-in-out infinite',
                  }}
                />
                <Bot
                  className="w-3 h-3"
                  style={{ color: 'var(--nous-fg-1)' }}
                  strokeWidth={1.7}
                />
                <span
                  className="font-nous-mono text-[10px] font-semibold"
                  style={{
                    color: 'var(--nous-fg-1)',
                    letterSpacing: '0.04em',
                  }}
                >
                  nous-agent
                </span>
                <span
                  className="font-nous-mono font-bold uppercase rounded-sm"
                  style={{
                    padding: '1px 5px',
                    fontSize: '8px',
                    letterSpacing: '0.12em',
                    background: 'var(--nous-aurum)',
                    color: 'var(--nous-sol-safe)',
                  }}
                >
                  Agent
                </span>
              </div>

              <button
                type="button"
                onClick={() => onRAGToggle(!enableRAG)}
                disabled={isLoading}
                aria-pressed={enableRAG}
                aria-label={
                  enableRAG ? 'Disable RAG context' : 'Enable RAG context'
                }
                title={
                  enableRAG
                    ? 'RAG enabled — click to disable'
                    : 'RAG disabled — click to enable'
                }
                className="inline-flex items-center gap-[7px] rounded-md shrink-0 transition-all disabled:opacity-50"
                style={{
                  padding: '4px 9px 4px 7px',
                  background: enableRAG ? 'var(--nous-aurum)' : 'transparent',
                  border: `1px solid ${
                    enableRAG
                      ? 'rgba(212, 160, 57, 0.25)'
                      : 'var(--nous-border-1)'
                  }`,
                }}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{
                    background: enableRAG
                      ? 'var(--nous-sol)'
                      : 'var(--nous-fg-3)',
                    boxShadow: enableRAG
                      ? '0 0 5px rgba(212,160,57,0.5)'
                      : 'none',
                  }}
                />
                <span
                  className="font-nous-mono text-[10px] font-semibold"
                  style={{
                    letterSpacing: '0.04em',
                    color: enableRAG
                      ? 'var(--nous-sol-safe)'
                      : 'var(--nous-fg-3)',
                  }}
                >
                  {isRAGLoading ? 'RETRIEVING' : enableRAG ? 'RAG' : 'RAG OFF'}
                </span>
              </button>

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

            <div
              className="inline-flex items-center gap-2 font-nous-mono text-[10px] tabular-nums whitespace-nowrap shrink-0"
              style={{
                color: isNearLimit ? 'var(--nous-corona)' : 'var(--nous-fg-3)',
                letterSpacing: '0.04em',
              }}
            >
              <span>
                {charCount}/{maxChars}
              </span>
              <span
                className="block rounded-sm overflow-hidden"
                style={{
                  width: '36px',
                  height: '3px',
                  background: 'var(--nous-border-1)',
                }}
              >
                <span
                  className="block h-full w-full origin-left rounded-sm"
                  style={{
                    transform: `scaleX(${fillPct / 100})`,
                    background: isNearLimit
                      ? 'var(--nous-corona)'
                      : 'var(--nous-sol)',
                    transition: 'transform 200ms ease-out',
                  }}
                />
              </span>
            </div>
          </div>

          {/* Body — serif input */}
          <div
            className="px-4 pt-3.5 pb-3"
            style={{ background: 'var(--nous-bg-2)' }}
          >
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              placeholder="Ask anything, or paste a passage to discuss…"
              rows={1}
              disabled={isDisabled}
              className="w-full bg-transparent resize-none outline-none font-nous-body text-[15px]"
              style={{
                color: 'var(--nous-fg-1)',
                lineHeight: '1.6',
                minHeight: '48px',
                maxHeight: '200px',
              }}
            />

            <div
              className="flex items-center justify-between mt-2.5 pt-2.5 border-t"
              style={{ borderColor: 'var(--nous-border-1)' }}
            >
              <div className="flex items-center gap-0.5">
                <label
                  className="grid place-items-center w-[30px] h-[30px] rounded-md cursor-pointer transition-all"
                  style={{ color: 'var(--nous-fg-3)' }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'var(--nous-aurum)';
                    e.currentTarget.style.color = 'var(--nous-sol-safe)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                    e.currentTarget.style.color = 'var(--nous-fg-3)';
                  }}
                  aria-label="Attach file"
                  title="Attach file"
                >
                  <Paperclip className="w-3.5 h-3.5" strokeWidth={1.7} />
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
                <label
                  className="grid place-items-center w-[30px] h-[30px] rounded-md cursor-pointer transition-all"
                  style={{ color: 'var(--nous-fg-3)' }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'var(--nous-aurum)';
                    e.currentTarget.style.color = 'var(--nous-sol-safe)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                    e.currentTarget.style.color = 'var(--nous-fg-3)';
                  }}
                  aria-label="Attach image"
                  title="Attach image"
                >
                  <ImageIcon className="w-3.5 h-3.5" strokeWidth={1.7} />
                  <input
                    type="file"
                    accept="image/*"
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
                <button
                  type="button"
                  onClick={toggleVoice}
                  disabled={!voiceSupported}
                  aria-pressed={isListening}
                  aria-label={
                    !voiceSupported
                      ? 'Voice input not supported'
                      : isListening
                        ? 'Stop voice input'
                        : 'Voice input'
                  }
                  title={
                    !voiceSupported
                      ? 'Voice input not supported'
                      : isListening
                        ? 'Stop voice input'
                        : 'Voice input'
                  }
                  className={cn(
                    'grid place-items-center w-[30px] h-[30px] rounded-md transition-all',
                    !voiceSupported && 'opacity-40 cursor-not-allowed'
                  )}
                  style={{
                    color: isListening
                      ? 'var(--nous-sol-safe)'
                      : 'var(--nous-fg-3)',
                    background: isListening
                      ? 'var(--nous-aurum)'
                      : 'transparent',
                  }}
                >
                  <Mic
                    className={cn(
                      'w-3.5 h-3.5',
                      isListening && 'animate-pulse'
                    )}
                    strokeWidth={1.7}
                  />
                </button>

                <span
                  className="inline-flex items-center gap-1.5 rounded-md ml-1.5 font-nous-mono text-[10px] select-none cursor-default"
                  style={{
                    padding: '4px 8px 4px 6px',
                    border: '1px dashed var(--nous-border-2)',
                    color: 'var(--nous-fg-3)',
                  }}
                  aria-label="Slash commands hint"
                  title="Type / to open commands"
                >
                  <kbd
                    className="font-nous-mono font-bold rounded-sm"
                    style={{
                      fontSize: '9px',
                      padding: '1px 4px',
                      background: 'var(--nous-bg-1)',
                      border: '1px solid var(--nous-border-1)',
                      color: 'var(--nous-fg-2)',
                    }}
                  >
                    /
                  </kbd>
                  Commands
                </span>
              </div>

              {isLoading ? (
                <button
                  onClick={onStop}
                  className="inline-flex items-center gap-2 font-medium rounded-lg transition-all active:scale-[0.97]"
                  style={{
                    padding: '8px 16px',
                    fontSize: '12px',
                    letterSpacing: '0.01em',
                    background: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid rgba(239, 68, 68, 0.4)',
                    color: 'var(--nous-mars)',
                  }}
                >
                  <Square className="w-3 h-3" strokeWidth={2.2} />
                  Stop
                </button>
              ) : (
                <button
                  onClick={onSubmit}
                  disabled={!value.trim() || isDisabled}
                  title="Send (Enter)"
                  className="group inline-flex items-center gap-2 font-semibold rounded-lg transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{
                    padding: '8px 16px',
                    fontSize: '12px',
                    letterSpacing: '0.01em',
                    background: 'var(--nous-erebus)',
                    color: 'white',
                    boxShadow: '0 1px 2px rgba(10,10,14,0.1)',
                  }}
                  onMouseEnter={(e) => {
                    if (!e.currentTarget.disabled) {
                      e.currentTarget.style.boxShadow =
                        '0 4px 12px rgba(10,10,14,0.12)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.boxShadow =
                      '0 1px 2px rgba(10,10,14,0.1)';
                  }}
                >
                  Send
                  <ArrowRight
                    className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5"
                    strokeWidth={2}
                  />
                </button>
              )}
            </div>
          </div>
        </motion.div>

        <div
          className="font-nous-mono text-[10px] text-center mt-2 opacity-60 hidden sm:block"
          style={{ color: 'var(--nous-fg-3)' }}
        >
          <kbd
            className="px-1.5 py-0.5 rounded-sm font-nous-mono text-[9px]"
            style={{
              background: 'var(--nous-bg-2)',
              border: '1px solid var(--nous-border-1)',
            }}
          >
            ↵
          </kbd>{' '}
          to send ·{' '}
          <kbd
            className="px-1.5 py-0.5 rounded-sm font-nous-mono text-[9px]"
            style={{
              background: 'var(--nous-bg-2)',
              border: '1px solid var(--nous-border-1)',
            }}
          >
            shift
          </kbd>
          +
          <kbd
            className="px-1.5 py-0.5 rounded-sm font-nous-mono text-[9px]"
            style={{
              background: 'var(--nous-bg-2)',
              border: '1px solid var(--nous-border-1)',
            }}
          >
            ↵
          </kbd>{' '}
          for newline ·{' '}
          <kbd
            className="px-1.5 py-0.5 rounded-sm font-nous-mono text-[9px]"
            style={{
              background: 'var(--nous-bg-2)',
              border: '1px solid var(--nous-border-1)',
            }}
          >
            /
          </kbd>{' '}
          for commands
        </div>
      </div>
    </div>
  );
}

export default ChatInput;
