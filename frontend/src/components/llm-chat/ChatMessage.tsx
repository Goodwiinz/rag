'use client';

import { User, Bot } from 'lucide-react';
import { MarkdownRenderer } from './MarkdownRenderer';
import { ChatMessageActions } from './ChatMessageActions';
import { formatTimestamp } from '@/lib/markdown-utils';
import type { Message } from '@/types/llm-chat';

interface ChatMessageProps {
  message: Message;
  index: number;
  onCopy: (content: string, index: number) => void;
  onEdit?: (index: number, content: string) => void;
  onDelete?: (index: number) => void;
  onRegenerate?: (index: number) => void;
  isCopied: boolean;
}

export function ChatMessage({
  message,
  index,
  onCopy,
  onEdit,
  onDelete,
  onRegenerate,
  isCopied,
}: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`group flex gap-4 \${isUser ? 'flex-row-reverse' : ''} animate-in fade-in slide-in-from-bottom-2 duration-500`}>
      <div className={`w-10 h-10 rounded-xl shrink-0 flex items-center justify-center border shadow-lg \${
        isUser
          ? 'bg-gradient-to-br from-purple-600 to-purple-700 border-purple-500 text-white shadow-purple-600/30'
          : 'bg-gradient-to-br from-[#1A1A1A] to-[#0E1015] border-[#27272A] text-gray-300 shadow-black/20'
      }`}>
        {isUser ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
      </div>

      <div className={`flex-1 max-w-[85%] \${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        <div className={`inline-block rounded-2xl px-6 py-4 text-sm leading-relaxed shadow-lg \${
          isUser
            ? 'bg-gradient-to-br from-purple-600 to-purple-700 text-white shadow-purple-600/20'
            : 'bg-[#1A1A1A] text-gray-300 border border-[#27272A] shadow-black/20'
        }`}>
          {message.role === 'assistant' ? (
            <MarkdownRenderer content={message.content} />
          ) : (
            <p className="whitespace-pre-wrap">{message.content}</p>
          )}
        </div>

        {message.timestamp && (
          <span className="text-xs text-gray-600 mt-2 px-1">
            {formatTimestamp(message.timestamp)}
          </span>
        )}

        <div className={`opacity-0 group-hover:opacity-100 transition-opacity mt-2 \${
          isUser ? 'flex-row-reverse' : 'flex-row'
        } flex`}>
          <ChatMessageActions
            message={message}
            index={index}
            onCopy={() => onCopy(message.content, index)}
            onEdit={onEdit ? () => onEdit(index, message.content) : undefined}
            onDelete={onDelete ? () => onDelete(index) : undefined}
            onRegenerate={onRegenerate ? () => onRegenerate(index) : undefined}
            isCopied={isCopied}
          />
        </div>
      </div>
    </div>
  );
}
