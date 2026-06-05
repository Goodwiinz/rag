'use client';

import { cn } from '@/lib/utils';
import { AVAILABLE_MODELS, ModelSelector } from './ModelSelector';
import {
  SlashCommandMenu,
  SLASH_LISTBOX_ID,
  slashOptionId,
} from './SlashCommandMenu';
import { useSlashCommandMenu } from './useSlashCommandMenu';
import type { SlashCommand, SlashCommandId } from './slashCommands';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import {
  ArrowRight,
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
  // Phase-aware status pill (shown only while generating)
  isStreaming?: boolean;
  streamingContent?: string;
  // Slash commands
  onCommand?: (id: SlashCommandId) => void;
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
  isStreaming,
  streamingContent,
  onCommand,
}: ChatInputProps) {
  const internalRef = useRef<HTMLTextAreaElement>(null);
  const textareaRef = inputRef ?? internalRef;
  const [isFocused, setIsFocused] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const reduceMotion = useReducedMotion();
  const menu = useSlashCommandMenu(value);
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

  const runCommand = (command: SlashCommand | undefined): void => {
    if (!command) return;
    onChange('');
    onCommand?.(command.id);
  };

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    // When the slash menu is open, intercept navigation/run keys. Enter runs
    // the highlighted command and never submits. The menu can only be open
    // while the whole value is a "/word" token, which is never a sendable
    // message — so normal send-on-Enter is unaffected.
    if (menu.isOpen && menu.filtered.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        menu.move(1);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        menu.move(-1);
        return;
      }
      if (e.key === 'Tab') {
        e.preventDefault();
        menu.move(e.shiftKey ? -1 : 1);
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        runCommand(menu.filtered[menu.highlightedIndex]);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        onChange('');
        return;
      }
    }
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

  const activeCommand =
    menu.isOpen && menu.filtered.length > 0
      ? menu.filtered[menu.highlightedIndex]
      : undefined;

  // Phase-aware status: shown only while generating.
  const statusPhase: 'retrieving' | 'writing' | 'reflecting' | null = !isLoading
    ? null
    : isRAGLoading
      ? 'retrieving'
      : isStreaming && (streamingContent?.length ?? 0) > 0
        ? 'writing'
        : 'reflecting';
  const statusLabel =
    statusPhase === 'retrieving'
      ? 'Nous is reading sources…'
      : statusPhase === 'writing'
        ? 'Nous is writing…'
        : 'Nous is reflecting…';

  return (
    <div
      className="z-40 px-2 sm:px-6 pt-3 pb-[80px] md:pb-4 border-t"
      style={{
        background: 'var(--nous-bg-1)',
        borderColor: 'var(--nous-border-1)',
      }}
    >
      <div className="relative max-w-[820px] mx-auto">
        <SlashCommandMenu
          open={menu.isOpen}
          commands={menu.filtered}
          highlightedIndex={menu.highlightedIndex}
          onHighlight={menu.setHighlightedIndex}
          onRun={runCommand}
        />
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
          {/* Top strip — live status, Ultra Thinking, model, counter */}
          <div
            className="flex items-center justify-between gap-2 px-3 py-2 border-b overflow-x-auto"
            style={{
              background: 'var(--nous-bg-1)',
              borderColor: 'var(--nous-border-1)',
            }}
          >
            <div className="flex items-center gap-2 min-w-0">
              <AnimatePresence>
                {statusPhase && (
                  <motion.div
                    key="nous-status"
                    role="status"
                    aria-live="polite"
                    initial={reduceMotion ? false : { opacity: 0, y: 2 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 2 }}
                    transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
                    className="inline-flex items-center gap-2 rounded-full shrink-0"
                    style={{
                      padding: '4px 11px 4px 9px',
                      background: 'var(--nous-bg-2)',
                      border: '1px solid var(--nous-border-1)',
                    }}
                  >
                    <span
                      className="w-1.5 h-1.5 rounded-full"
                      style={{
                        background: 'var(--nous-sol)',
                        boxShadow: '0 0 0 3px rgba(212, 160, 57, 0.18)',
                        animation: 'nous-pulse 1.4s ease-in-out infinite',
                      }}
                    />
                    <span
                      className="font-nous-mono text-[10px] font-medium"
                      style={{
                        color: 'var(--nous-fg-2)',
                        letterSpacing: '0.02em',
                      }}
                    >
                      {statusLabel}
                    </span>
                  </motion.div>
                )}
              </AnimatePresence>

              <button
                type="button"
                onClick={() => onRAGToggle(!enableRAG)}
                disabled={isLoading}
                aria-pressed={enableRAG}
                aria-label={
                  enableRAG
                    ? 'Ultra Thinking on. Grounds answers in your sources.'
                    : 'Ultra Thinking off. Answers without your sources.'
                }
                title={
                  enableRAG
                    ? 'Ultra Thinking on. Grounds answers in your sources.'
                    : 'Ultra Thinking off. Answers without your sources.'
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
                  className="font-nous-mono text-[10px] font-semibold whitespace-nowrap"
                  style={{
                    letterSpacing: '0.04em',
                    color: enableRAG
                      ? 'var(--nous-sol-safe)'
                      : 'var(--nous-fg-3)',
                  }}
                >
                  Ultra Thinking
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
              aria-expanded={menu.isOpen}
              aria-controls={menu.isOpen ? SLASH_LISTBOX_ID : undefined}
              aria-activedescendant={
                activeCommand ? slashOptionId(activeCommand.id) : undefined
              }
              aria-autocomplete="list"
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

                <button
                  type="button"
                  onClick={() => {
                    onChange('/');
                    textareaRef.current?.focus();
                  }}
                  className="inline-flex items-center gap-1.5 rounded-md ml-1.5 font-nous-mono text-[10px] cursor-pointer transition-colors hover:border-[var(--nous-sol)]/40"
                  style={{
                    padding: '4px 8px 4px 6px',
                    border: '1px dashed var(--nous-border-2)',
                    color: 'var(--nous-fg-3)',
                  }}
                  aria-label="Open commands"
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
                </button>
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
