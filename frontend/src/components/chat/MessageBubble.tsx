'use client';

import React, { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { IconButton, IconButtonSm } from '@/components/ui/icon-button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';
import { cn } from '@/lib/utils';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Bot,
  User,
  Copy,
  Check,
  RefreshCw,
  ThumbsUp,
  ThumbsDown,
  Bookmark,
  Share,
  MoreVertical,
  MessageSquare,
  Clock,
  Zap,
} from 'lucide-react';

interface MessageBubbleProps {
  message: {
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp?: number;
    id?: string;
  };
  isTyping?: boolean;
  isLast?: boolean;
  onCopy?: (content: string) => Promise<void>;
  onRegenerate?: () => void;
  onReaction?: (type: 'like' | 'dislike') => void;
  isCopied?: boolean;
  reaction?: 'like' | 'dislike' | null;
  isBookmarked?: boolean;
  onBookmark?: () => void;
  onShare?: () => void;
  modelInfo?: {
    name: string;
    responseTime?: number;
    tokens?: number;
  };
  className?: string;
}

export function MessageBubble({
  message,
  isTyping = false,
  isLast = false,
  onCopy,
  onRegenerate,
  onReaction,
  isCopied = false,
  reaction = null,
  isBookmarked = false,
  onBookmark,
  onShare,
  modelInfo,
  className,
}: MessageBubbleProps) {
  const messageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isLast && messageRef.current) {
      messageRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [isLast]);

  const formatTimestamp = (timestamp?: number) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString();
  };

  const copyToClipboard = async () => {
    if (onCopy) {
      await onCopy(message.content);
    }
  };

  const isUser = message.role === 'user';

  return (
    <motion.div
      ref={messageRef}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className={cn(
        'group relative flex gap-3 mb-6',
        isUser && 'flex-row-reverse',
        className
      )}
    >
      {/* Avatar */}
      <Avatar className="w-8 h-8 shrink-0">
        <AvatarFallback
          className={cn(
            'text-xs font-medium transition-colors',
            isUser
              ? 'bg-gradient-to-br from-[#ffb700] to-[#cc9200] text-[#0a0a0f]'
              : 'bg-gradient-to-br from-[#D4A039] to-[#B8882F] text-[#0a0a0f]'
          )}
        >
          {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
        </AvatarFallback>
      </Avatar>

      {/* Message Content */}
      <div className={cn('flex-1 space-y-2 min-w-0', isUser && 'items-end')}>
        {/* Header */}
        <div
          className={cn(
            'flex items-center gap-2',
            isUser ? 'justify-end' : 'justify-start'
          )}
        >
          <span className="text-xs font-medium text-muted-foreground">
            {isUser ? 'You' : 'Assistant'}
          </span>

          {!isUser && modelInfo && (
            <HoverCard>
              <HoverCardTrigger>
                <Badge variant="secondary" className="text-xs">
                  <Zap className="w-3 h-3 mr-1" />
                  {modelInfo.name}
                </Badge>
              </HoverCardTrigger>
              <HoverCardContent className="w-48">
                <div className="space-y-2">
                  {modelInfo.responseTime && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">
                        Response time
                      </span>
                      <span>{(modelInfo.responseTime / 1000).toFixed(2)}s</span>
                    </div>
                  )}
                  {modelInfo.tokens && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Tokens</span>
                      <span>{modelInfo.tokens}</span>
                    </div>
                  )}
                </div>
              </HoverCardContent>
            </HoverCard>
          )}

          {message.timestamp && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="w-3 h-3" />
              <span>{formatTimestamp(message.timestamp)}</span>
            </div>
          )}
        </div>

        {/* Message Bubble */}
        <div
          className={cn(
            'relative rounded-2xl px-4 py-3 shadow-sm transition-all hover:shadow-md',
            isUser
              ? 'bg-gradient-to-br from-[#ffb700] to-[#cc9200] text-[#0a0a0f] ml-auto max-w-[80%] shadow-[0_0_15px_rgba(255,183,0,0.15)]'
              : 'bg-[var(--terminal-surface)] border border-[var(--terminal-border)] max-w-[90%] hover:border-[var(--phosphor-green)]/30'
          )}
        >
          {isTyping ? (
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 bg-current rounded-full animate-bounce opacity-60" />
              <span
                className="w-2 h-2 bg-current rounded-full animate-bounce opacity-60"
                style={{ animationDelay: '0.2s' }}
              />
              <span
                className="w-2 h-2 bg-current rounded-full animate-bounce opacity-60"
                style={{ animationDelay: '0.4s' }}
              />
              <span className="text-xs ml-2 opacity-70">
                Assistant is typing
              </span>
            </div>
          ) : (
            <div
              className={cn(
                'text-sm leading-relaxed',
                isUser ? 'text-white' : 'text-foreground'
              )}
            >
              {isUser ? (
                <p className="whitespace-pre-wrap break-words">
                  {message.content}
                </p>
              ) : (
                <ReactMarkdown
                  components={{
                    code({ node, className, children, ...props }) {
                      const match = /language-(\w+)/.exec(className || '');
                      const language = match ? match[1] : '';
                      // Detect inline code by checking if there's no language specified
                      const isInline = !language;

                      return !isInline && language ? (
                        <div className="relative group">
                          <div className="flex items-center justify-between bg-muted px-4 py-2 border-b border-border rounded-t-lg">
                            <span className="text-xs font-medium text-muted-foreground">
                              {language}
                            </span>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 px-2 opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={() =>
                                navigator.clipboard.writeText(
                                  String(children).replace(/\n$/, '')
                                )
                              }
                              aria-label="Copy code to clipboard"
                            >
                              <Copy className="w-3 h-3" />
                            </Button>
                          </div>
                          <SyntaxHighlighter
                            style={
                              oneDark as { [key: string]: React.CSSProperties }
                            }
                            language={language}
                            PreTag="div"
                            className="!mt-0 !rounded-t-none"
                          >
                            {String(children).replace(/\n$/, '')}
                          </SyntaxHighlighter>
                        </div>
                      ) : (
                        <code
                          className={cn(
                            'rounded-md bg-muted px-1.5 py-0.5 text-xs font-mono',
                            !isInline && 'block'
                          )}
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    },
                    a: ({ href, children }) => (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#00d4ff] hover:text-[#D4A039] underline underline-offset-2 transition-colors"
                      >
                        {children}
                      </a>
                    ),
                    blockquote: ({ children }) => (
                      <blockquote className="border-l-4 border-[#D4A039]/30 pl-4 italic text-[#a1a1aa]">
                        {children}
                      </blockquote>
                    ),
                    table: ({ children }) => (
                      <div className="overflow-x-auto my-2">
                        <table className="min-w-full divide-y divide-border">
                          {children}
                        </table>
                      </div>
                    ),
                    th: ({ children }) => (
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/50">
                        {children}
                      </th>
                    ),
                    td: ({ children }) => (
                      <td className="px-3 py-2 text-sm border-t border-border">
                        {children}
                      </td>
                    ),
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              )}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        {!isTyping && (
          <div
            className={cn(
              'flex items-center gap-1 transition-all',
              isUser ? 'justify-end' : 'justify-start',
              'opacity-0 group-hover:opacity-100'
            )}
          >
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={copyToClipboard}
            >
              {isCopied ? (
                <>
                  <Check className="w-3 h-3 mr-1" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3 mr-1" />
                  Copy
                </>
              )}
            </Button>

            {!isUser && onRegenerate && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={onRegenerate}
              >
                <RefreshCw className="w-3 h-3 mr-1" />
                Regenerate
              </Button>
            )}

            {!isUser && onReaction && (
              <>
                <Button
                  variant={reaction === 'like' ? 'secondary' : 'ghost'}
                  size="sm"
                  className={cn(
                    'h-7 px-2 text-xs',
                    reaction === 'like' && 'text-[#D4A039]'
                  )}
                  onClick={() => onReaction('like')}
                >
                  <ThumbsUp className="w-3 h-3 mr-1" />
                  Like
                </Button>
                <Button
                  variant={reaction === 'dislike' ? 'secondary' : 'ghost'}
                  size="sm"
                  className={cn(
                    'h-7 px-2 text-xs',
                    reaction === 'dislike' && 'text-red-600'
                  )}
                  onClick={() => onReaction('dislike')}
                >
                  <ThumbsDown className="w-3 h-3 mr-1" />
                  Dislike
                </Button>
              </>
            )}

            {!isUser && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <IconButtonSm
                    icon={<MoreVertical className="w-3 h-3" />}
                    label="More actions"
                    className="h-7 w-7"
                  />
                </DropdownMenuTrigger>
                <DropdownMenuContent align={isUser ? 'end' : 'start'}>
                  {onBookmark && (
                    <DropdownMenuItem onClick={onBookmark}>
                      <Bookmark
                        className={cn(
                          'w-4 h-4 mr-2',
                          isBookmarked && 'fill-current text-[#ffb700]'
                        )}
                      />
                      {isBookmarked ? 'Remove bookmark' : 'Bookmark'}
                    </DropdownMenuItem>
                  )}
                  {onShare && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={onShare}>
                        <Share className="w-4 h-4 mr-2" />
                        Share message
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}

export default MessageBubble;
