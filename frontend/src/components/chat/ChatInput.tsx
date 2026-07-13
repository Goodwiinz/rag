'use client';

import { ComposerPrimitive } from '@assistant-ui/react';
import { cn } from '@/lib/utils';
import {
  SlashCommandMenu,
  SLASH_LISTBOX_ID,
  slashOptionId,
} from './SlashCommandMenu';
import { useSlashCommandMenu } from './useSlashCommandMenu';
import type { SlashCommand, SlashCommandId } from './slashCommands';
import {
  ArrowRight,
  Image as ImageIcon,
  Mic,
  Paperclip,
  Square,
  X,
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
  inputRef?: React.RefObject<HTMLTextAreaElement>;
  onAttach?: (files: FileList) => void;
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
  inputRef,
  onAttach,
  onCommand,
}: ChatInputProps) {
  const internalRef = useRef<HTMLTextAreaElement>(null);
  const textareaRef = inputRef ?? internalRef;
  const [isFocused, setIsFocused] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const menu = useSlashCommandMenu(value);

  // Local attachment receipts — chips shown in the composer for files the user
  // attached this turn. The page still owns the actual upload via onAttach;
  // these are the visual record (with image thumbnails) the composer lacked.
  type Attachment = {
    id: string;
    name: string;
    isImage: boolean;
    url?: string;
  };
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  // Keep a live ref so the unmount cleanup revokes the current object URLs
  // without re-running on every attachment change.
  const attachmentsRef = useRef<Attachment[]>(attachments);
  attachmentsRef.current = attachments;

  const addFiles = (files: FileList): void => {
    const next: Attachment[] = Array.from(files).map((file) => {
      const isImage = file.type.startsWith('image/');
      return {
        id: `${file.name}-${file.size}-${file.lastModified}`,
        name: file.name,
        isImage,
        url: isImage ? URL.createObjectURL(file) : undefined,
      };
    });
    setAttachments((prev) => [...prev, ...next]);
    onAttach?.(files);
  };

  const removeAttachment = (id: string): void => {
    setAttachments((prev) => {
      const target = prev.find((a) => a.id === id);
      if (target?.url) URL.revokeObjectURL(target.url);
      return prev.filter((a) => a.id !== id);
    });
  };

  // Clear composer chips + revoke their blob URLs once a message is sent —
  // otherwise stale chips linger into the next turn and every image object URL
  // leaks until unmount.
  const clearAttachments = (): void => {
    setAttachments((prev) => {
      prev.forEach((a) => a.url && URL.revokeObjectURL(a.url));
      return [];
    });
  };

  useEffect(() => {
    setVoiceSupported(getSpeechRecognition() !== null);
  }, []);

  useEffect(() => {
    return () => {
      attachmentsRef.current.forEach(
        (a) => a.url && URL.revokeObjectURL(a.url)
      );
    };
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
        menu.dismiss();
        return;
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && value.trim() && !isOverLimit) {
        onSubmit();
        clearAttachments();
      }
    }
  };

  const handleComposerSubmit = (e: React.FormEvent<HTMLFormElement>): void => {
    e.preventDefault();
    if (!isLoading && value.trim() && !isOverLimit) {
      onSubmit();
      clearAttachments();
    }
  };

  const isDisabled = isLoading;
  const charCount = value.length;
  const maxChars = 4000;
  const fillPct = Math.min(100, Math.round((charCount / maxChars) * 100));
  const isNearLimit = charCount > maxChars * 0.8;
  const isOverLimit = charCount > maxChars;

  const activeCommand =
    menu.isOpen && menu.filtered.length > 0
      ? menu.filtered[menu.highlightedIndex]
      : undefined;

  return (
    <div
      className="z-40 px-2 sm:px-6 pt-3 pb-[calc(68px+env(safe-area-inset-bottom))] md:pb-4 border-t"
      style={{
        background: 'var(--nous-bg-1)',
        borderColor: 'var(--nous-border-1)',
      }}
    >
      <div className="relative max-w-(--nous-chat-col) mx-auto">
        <SlashCommandMenu
          open={menu.isOpen}
          commands={menu.filtered}
          highlightedIndex={menu.highlightedIndex}
          onHighlight={menu.setHighlightedIndex}
          onRun={runCommand}
        />
        <ComposerPrimitive.Root
          onSubmit={handleComposerSubmit}
          className="rounded-[14px] overflow-hidden"
          style={{
            background: 'var(--nous-bg-2)',
            border: `1px solid ${
              isFocused
                ? 'rgba(var(--nous-sol-rgb), 0.4)'
                : 'var(--nous-border-1)'
            }`,
            boxShadow: isFocused
              ? '0 0 0 3px rgba(var(--nous-sol-rgb), 0.10), 0 8px 24px rgba(var(--nous-erebus-rgb), 0.06)'
              : '0 1px 2px rgba(var(--nous-erebus-rgb), 0.04)',
            transition:
              'border-color 260ms var(--nous-ease-out), box-shadow 260ms var(--nous-ease-out)',
          }}
        >
          {/* Top strip — live status, Ultra Thinking, counter */}
          <div
            className="flex items-center justify-between gap-2 px-3 py-2 border-b"
            style={{
              background: 'var(--nous-bg-1)',
              borderColor: 'var(--nous-border-1)',
            }}
          >
            <div className="flex items-center gap-2 min-w-0">
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
                      ? 'rgba(var(--nous-sol-rgb), 0.25)'
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
                      ? '0 0 5px rgba(var(--nous-sol-rgb), 0.5)'
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
            </div>

            <div
              className="inline-flex items-center gap-2 font-nous-mono text-[10px] tabular-nums whitespace-nowrap shrink-0"
              style={{
                color: isOverLimit
                  ? 'var(--nous-mars)'
                  : isNearLimit
                    ? 'var(--nous-corona)'
                    : 'var(--nous-fg-3)',
                letterSpacing: '0.04em',
              }}
            >
              <span
                className="hidden sm:inline"
                aria-live="polite"
                aria-atomic="true"
              >
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
            {attachments.length > 0 && (
              <ul
                className="flex flex-wrap items-center gap-2 mb-3 list-none p-0 m-0"
                aria-label="Attached files"
              >
                {attachments.map((att) => (
                  <li
                    key={att.id}
                    className="group inline-flex items-center gap-2 h-9 rounded-md pl-1.5 pr-1 font-nous-mono text-[11px]"
                    style={{
                      background: 'var(--nous-bg-1)',
                      border: '1px solid var(--nous-border-1)',
                      color: 'var(--nous-fg-2)',
                    }}
                  >
                    {att.isImage && att.url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={att.url}
                        alt={att.name}
                        className="w-6 h-6 rounded object-cover shrink-0"
                      />
                    ) : (
                      <span
                        className="grid place-items-center w-6 h-6 rounded shrink-0"
                        style={{
                          background: 'var(--nous-bg-2)',
                          color: 'var(--nous-fg-3)',
                        }}
                      >
                        <Paperclip className="w-3 h-3" strokeWidth={1.7} />
                      </span>
                    )}
                    <span className="max-w-[140px] truncate" title={att.name}>
                      {att.name}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeAttachment(att.id)}
                      aria-label={`Remove ${att.name}`}
                      title="Remove"
                      className="grid place-items-center w-6 h-6 rounded transition-colors hover:bg-(--nous-aurum)"
                      style={{ color: 'var(--nous-fg-3)' }}
                    >
                      <X className="w-3 h-3" strokeWidth={2} />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <ComposerPrimitive.Input asChild>
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
                aria-invalid={isOverLimit || undefined}
                aria-describedby={isOverLimit ? 'nous-input-limit' : undefined}
                className="w-full bg-transparent resize-none outline-hidden font-nous-body text-[16px]"
                style={{
                  color: 'var(--nous-fg-1)',
                  lineHeight: '1.6',
                  minHeight: '48px',
                  maxHeight: '200px',
                }}
              />
            </ComposerPrimitive.Input>

            {isOverLimit && (
              <p
                id="nous-input-limit"
                role="alert"
                className="mt-2 font-nous-mono text-[10px]"
                style={{ color: 'var(--nous-mars)', letterSpacing: '0.02em' }}
              >
                Message is {charCount - maxChars} characters over the {maxChars}{' '}
                limit. Trim it to send.
              </p>
            )}

            <div
              className="flex items-center justify-between mt-2.5 pt-2.5 border-t"
              style={{ borderColor: 'var(--nous-border-1)' }}
            >
              <div className="flex items-center gap-0.5">
                <label
                  className="grid place-items-center w-11 h-11 rounded-md cursor-pointer transition-all"
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
                      if (files && files.length > 0) {
                        addFiles(files);
                      }
                      e.target.value = '';
                    }}
                  />
                </label>
                <label
                  className="grid place-items-center w-11 h-11 rounded-md cursor-pointer transition-all"
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
                      if (files && files.length > 0) {
                        addFiles(files);
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
                    'grid place-items-center w-11 h-11 rounded-md transition-all',
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
                  className="inline-flex items-center gap-1.5 rounded-md ml-1.5 min-h-[44px] font-nous-mono text-[10px] cursor-pointer transition-colors hover:bg-(--nous-aurum)"
                  style={{
                    padding: '4px 8px',
                    border: '1px solid var(--nous-border-1)',
                    background: 'var(--nous-bg-1)',
                    color: 'var(--nous-fg-2)',
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
                  type="button"
                  onClick={onStop}
                  className="inline-flex items-center gap-2 font-medium rounded-lg transition-all active:scale-[0.97]"
                  style={{
                    padding: '8px 16px',
                    fontSize: '12px',
                    letterSpacing: '0.01em',
                    background: 'rgba(var(--nous-mars-rgb), 0.1)',
                    border: '1px solid rgba(var(--nous-mars-rgb), 0.4)',
                    color: 'var(--nous-mars)',
                  }}
                >
                  <Square className="w-3 h-3" strokeWidth={2.2} />
                  Stop
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!value.trim() || isDisabled || isOverLimit}
                  title={
                    isOverLimit
                      ? `Message is over the ${maxChars}-character limit`
                      : 'Send (Enter)'
                  }
                  className="group inline-flex items-center gap-2 font-semibold rounded-lg transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100"
                  style={{
                    padding: '8px 16px',
                    fontSize: '12px',
                    letterSpacing: '0.01em',
                    background: 'var(--nous-sol)',
                    color: 'var(--nous-erebus)',
                    boxShadow: '0 1px 2px rgba(var(--nous-sol-rgb), 0.2)',
                  }}
                  onMouseEnter={(e) => {
                    if (!e.currentTarget.disabled) {
                      e.currentTarget.style.background = 'var(--nous-helios)';
                      e.currentTarget.style.boxShadow =
                        '0 4px 12px rgba(var(--nous-sol-rgb), 0.3)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'var(--nous-sol)';
                    e.currentTarget.style.boxShadow =
                      '0 1px 2px rgba(var(--nous-sol-rgb), 0.2)';
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
        </ComposerPrimitive.Root>

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
