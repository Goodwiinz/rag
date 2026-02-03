'use client';

import { Button } from '@/components/ui/button';
import { IconButton } from '@/components/ui/icon-button';
import { Textarea } from '@/components/ui/textarea';
import {
    TooltipProvider
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { AnimatePresence, motion } from 'framer-motion';
import {
    Bold,
    Code,
    Italic,
    Link2,
    List,
    ListOrdered,
    Mic,
    Paperclip,
    Quote,
    Send,
    Settings,
    Square,
    Trash2
} from 'lucide-react';
import React, { useCallback, useEffect, useRef, useState } from 'react';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop?: () => void;
  isLoading?: boolean;
  disabled?: boolean;
  placeholder?: string;
  maxLength?: number;
  showWordCount?: boolean;
  showToolbar?: boolean;
  allowFileUpload?: boolean;
  allowVoiceInput?: boolean;
  onFileUpload?: (files: File[]) => void;
  onVoiceRecord?: (blob: Blob) => void;
  className?: string;
}

interface FormattingButton {
  icon: React.ReactNode;
  title: string;
  action: () => void;
  shortcut?: string;
}

export function ChatInput({
  value,
  onChange,
  onSubmit,
  onStop,
  isLoading = false,
  disabled = false,
  placeholder = "Type your message...",
  maxLength = 4000,
  showWordCount = true,
  showToolbar = true,
  allowFileUpload = true,
  allowVoiceInput = true,
  onFileUpload,
  onVoiceRecord,
  className,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [isToolbarOpen, setIsToolbarOpen] = useState(false);
  const [showFormattingHelp, setShowFormattingHelp] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      const scrollHeight = Math.min(textarea.scrollHeight, 200);
      textarea.style.height = `${scrollHeight}px`;
    }
  }, [value]);

  // Focus textarea on mount
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  // Handle keyboard shortcuts
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && value.trim()) {
        onSubmit();
      }
    }

    // Ctrl/Cmd + B for bold
    if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
      e.preventDefault();
      insertFormatting('**', '**');
    }

    // Ctrl/Cmd + I for italic
    if ((e.ctrlKey || e.metaKey) && e.key === 'i') {
      e.preventDefault();
      insertFormatting('*', '*');
    }

    // Ctrl/Cmd + K for code
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      insertFormatting('`', '`');
    }
  };

  // Insert text formatting at cursor position
  const insertFormatting = (prefix: string, suffix: string) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = value.substring(start, end);
    const formattedText = `${prefix}${selectedText}${suffix}`;

    const newValue = value.substring(0, start) + formattedText + value.substring(end);
    onChange(newValue);

    // Restore cursor position
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(
        start + prefix.length,
        start + prefix.length + selectedText.length
      );
    }, 0);
  };

  // Formatting buttons
  const formattingButtons: FormattingButton[] = [
    {
      icon: <Bold className="w-4 h-4" />,
      title: 'Bold (Ctrl+B)',
      action: () => insertFormatting('**', '**'),
      shortcut: 'Ctrl+B',
    },
    {
      icon: <Italic className="w-4 h-4" />,
      title: 'Italic (Ctrl+I)',
      action: () => insertFormatting('*', '*'),
      shortcut: 'Ctrl+I',
    },
    {
      icon: <Code className="w-4 h-4" />,
      title: 'Inline code (Ctrl+K)',
      action: () => insertFormatting('`', '`'),
      shortcut: 'Ctrl+K',
    },
    {
      icon: <List className="w-4 h-4" />,
      title: 'Bullet list',
      action: () => insertFormatting('- ', ''),
    },
    {
      icon: <ListOrdered className="w-4 h-4" />,
      title: 'Numbered list',
      action: () => insertFormatting('1. ', ''),
    },
    {
      icon: <Quote className="w-4 h-4" />,
      title: 'Quote',
      action: () => insertFormatting('> ', ''),
    },
    {
      icon: <Link2 className="w-4 h-4" />,
      title: 'Link',
      action: () => insertFormatting('[', '](url)'),
    },
  ];

  // Handle file upload
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0 && onFileUpload) {
      onFileUpload(files);
    }
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Voice recording handlers
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      const chunks: BlobPart[] = [];

      mediaRecorder.ondataavailable = (e) => {
        chunks.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunks, { type: 'audio/webm' });
        if (onVoiceRecord) {
          onVoiceRecord(blob);
        }
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      mediaRecorderRef.current = mediaRecorder;
      setIsRecording(true);
      setRecordingTime(0);

      // Update recording time
      recordingIntervalRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    } catch (error) {
      console.error('Error accessing microphone:', error);
    }
  }, [onVoiceRecord]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setRecordingTime(0);

      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
      }
    }
  }, [isRecording]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
      }
      if (isRecording) {
        stopRecording();
      }
    };
  }, [isRecording, stopRecording]);

  // Format recording time
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Count words and characters
  const wordCount = value.trim().split(/\s+/).filter(word => word.length > 0).length;
  // Character count logic
  const charCount = value.length;
  const charPercentage = (charCount / maxLength) * 100;
  const showCharCount = showWordCount && (charPercentage > 70 || (textareaRef.current && document.activeElement === textareaRef.current));

  return (
    <TooltipProvider>
      <div className={cn("relative w-full", className)}>
        {/* Formatting Toolbar */}
        <AnimatePresence>
          {isToolbarOpen && showToolbar && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              className="absolute bottom-full left-0 right-0 mb-2 p-2 bg-popover border rounded-lg shadow-lg"
            >
              <div className="flex items-center gap-1 flex-wrap">
                {formattingButtons.map((button, idx) => (
                  <IconButton
                    key={idx}
                    icon={button.icon}
                    label={button.title}
                    onClick={button.action}
                    className="h-8 w-8"
                    size="sm"
                  />
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Main Input Area */}
        <div className="relative group">
          {/* File Input (Hidden) */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*,.pdf,.txt,.md,.doc,.docx"
            onChange={handleFileSelect}
            className="hidden"
          />

          {/* Textarea */}
          <Textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value.slice(0, maxLength))}
            onKeyDown={handleKeyDown}
            placeholder={disabled ? "Disabled..." : placeholder}
            disabled={disabled || isLoading || isRecording}
            className={cn(
              "min-h-[60px] max-h-[200px] resize-none pr-28 transition-all",
              "border-2 shadow-sm focus:shadow-md",
              "focus:ring-2 focus:ring-[#00ff9f]/20 focus:border-[#00ff9f]",
              disabled && "opacity-50 cursor-not-allowed"
            )}
            rows={1}
          />

          {/* Left Actions */}
          <div className="absolute left-3 bottom-3 flex items-center gap-1">
            {/* Toggle Toolbar */}
            {showToolbar && (
              <IconButton
                icon={<Settings className="w-3 h-3" />}
                label="Formatting tools"
                className={cn(
                  "h-7 w-7 transition-opacity",
                  "opacity-100 md:opacity-0 md:group-hover:opacity-100 md:focus-within:opacity-100",
                  isToolbarOpen && "opacity-100"
                )}
                onClick={() => setIsToolbarOpen(!isToolbarOpen)}
                disabled={disabled || isLoading}
              />
            )}

            {/* File Upload */}
            {allowFileUpload && onFileUpload && (
              <IconButton
                icon={<Paperclip className="w-3 h-3" />}
                label="Attach files"
                className={cn(
                  "h-7 w-7 transition-opacity",
                  "opacity-100 md:opacity-0 md:group-hover:opacity-100 md:focus-within:opacity-100"
                )}
                onClick={() => fileInputRef.current?.click()}
                disabled={disabled || isLoading || isRecording}
              />
            )}

            {/* Voice Recording */}
            {allowVoiceInput && onVoiceRecord && (
              <AnimatePresence>
                {isRecording ? (
                  <motion.div
                    initial={{ scale: 0.8 }}
                    animate={{ scale: 1 }}
                    exit={{ scale: 0.8 }}
                    className="flex items-center gap-2 bg-red-500 text-white px-2 py-1 rounded-full"
                  >
                    <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
                    <span className="text-xs font-medium">{formatTime(recordingTime)}</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-5 w-5 text-white hover:bg-white/20"
                      onClick={stopRecording}
                      aria-label="Stop recording"
                    >
                      <Square className="w-3 h-3 fill-current" />
                    </Button>
                  </motion.div>
                ) : (
                  <IconButton
                    icon={<Mic className="w-3 h-3" />}
                    label="Voice input"
                    className={cn(
                      "h-7 w-7 transition-opacity",
                      "opacity-100 md:opacity-0 md:group-hover:opacity-100 md:focus-within:opacity-100"
                    )}
                    onClick={startRecording}
                    disabled={disabled || isLoading}
                  />
                )}
              </AnimatePresence>
            )}
          </div>

          {/* Right Actions */}
          <div className="absolute right-3 bottom-3 flex items-center gap-1">
            {/* Clear Input */}
            {value && (
              <AnimatePresence>
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                >
                  <IconButton
                    icon={<Trash2 className="w-3 h-3" />}
                    label="Clear input"
                    className="h-7 w-7"
                    onClick={() => onChange('')}
                    disabled={disabled || isLoading}
                  />
                </motion.div>
              </AnimatePresence>
            )}

            {/* Send/Stop Button */}
            <Button
              type="button"
              onClick={isLoading && onStop ? onStop : onSubmit}
              disabled={
                disabled ||
                (!isLoading && !value.trim()) ||
                isRecording
              }
              size="sm"
              aria-label={isLoading ? "Stop generation" : "Send message"}
              className={cn(
                "h-8 min-w-[32px] transition-all shadow-lg",
                isLoading
                  ? "bg-red-500 hover:bg-red-600 text-white"
                  : "bg-gradient-to-r from-[#00ff9f] to-[#00cc7a] hover:from-[#00cc7a] hover:to-[#00994d] text-[#0a0a0f] font-medium hover:shadow-[0_0_20px_rgba(0,255,159,0.3)]"
              )}
            >
              {isLoading ? (
                <Square className="w-4 h-4" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>

          {/* Character Count Indicator */}
          <div
            className={cn(
              "absolute -top-6 right-0 text-xs transition-all duration-200",
              showCharCount || charPercentage > 70 ? "opacity-100" : "opacity-0",
              charPercentage > 90
                ? "text-destructive font-medium"
                : charPercentage > 70
                ? "text-amber-500"
                : "text-muted-foreground"
            )}
            aria-live="polite"
            aria-atomic="true"
          >
            {charCount.toLocaleString()}/{maxLength.toLocaleString()}
            {charPercentage > 90 && (
              <span className="ml-1">
                ({Math.floor(maxLength - charCount)} remaining)
              </span>
            )}
          </div>
        </div>

        {/* Formatting Help */}
        {showFormattingHelp && (
          <div className="mt-2 p-3 bg-muted/50 rounded-lg text-xs text-muted-foreground">
            <p className="font-medium mb-1">Markdown shortcuts:</p>
            <div className="grid grid-cols-2 gap-2">
              <div>• **text** for bold</div>
              <div>• *text* for italic</div>
              <div>• `code` for inline code</div>
              <div>• ```code``` for code blocks</div>
              <div>• - item for bullet lists</div>
              <div>• 1. item for numbered lists</div>
            </div>
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}

export default ChatInput;