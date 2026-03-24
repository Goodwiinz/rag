'use client';

import { useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send, Square, Zap } from 'lucide-react';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  isLoading: boolean;
  isModelLoading: boolean;
  selectedModel: string | null;
  disabled?: boolean;
}

export function ChatInput({
  value,
  onChange,
  onSubmit,
  onStop,
  isLoading,
  isModelLoading,
  selectedModel,
  disabled = false,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!isModelLoading && selectedModel && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isModelLoading, selectedModel]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className="p-6 pt-3">
      <div className="max-w-4xl mx-auto">
        <div
          className={`relative rounded-2xl border bg-[#0E1015] shadow-2xl transition-all \${
          isModelLoading || disabled
            ? 'opacity-50 pointer-events-none border-[#27272A]'
            : 'border-[#27272A] focus-within:border-purple-500/50 focus-within:shadow-purple-500/20'
        }`}
        >
          <Textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              selectedModel
                ? 'Type your message... (Shift+Enter for new line)'
                : 'Select a model above to start chatting...'
            }
            className="w-full bg-transparent border-0 rounded-2xl py-5 pl-6 pr-16 text-white placeholder:text-gray-600 focus:ring-0 resize-none min-h-[70px] max-h-[200px]"
            rows={1}
            disabled={!selectedModel || isModelLoading || disabled}
          />
          <div className="absolute right-3 bottom-3 flex items-center gap-2">
            {isLoading ? (
              <Button
                onClick={onStop}
                size="icon"
                aria-label="Stop generating"
                className="h-10 w-10 rounded-xl bg-red-500/10 text-red-500 hover:bg-red-500/20 border border-red-500/20 shadow-lg"
              >
                <Square className="w-4 h-4" />
              </Button>
            ) : (
              <Button
                onClick={onSubmit}
                disabled={!value.trim() || !selectedModel}
                size="icon"
                aria-label="Send message"
                className={`h-10 w-10 rounded-xl transition-all shadow-lg \${
                  value.trim() && selectedModel
                    ? 'bg-gradient-to-br from-purple-600 to-purple-700 hover:from-purple-500 hover:to-purple-600 text-white shadow-purple-600/30 hover:shadow-purple-600/50'
                    : 'bg-[#1A1A1A] text-gray-600 hover:bg-[#252525] shadow-black/20'
                }`}
              >
                <Send className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
