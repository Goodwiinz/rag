'use client';

import {
  ChatSettings,
  Model,
  CitationRenderer,
  CitationPanel,
} from '@/components/chat';
import { Citation } from '@/utils/citationParser';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/authStore';
import { useChatStore } from '@/store/chat-store';
import { workspaceService } from '@/services/workspaceService';
import apiClient from '@/services/apiClient';
import {
  Workspace,
  Conversation as DBConversation,
  Thread,
  ChatMessage as DBChatMessage,
  MessageRole,
} from '@/types/workspace';
import { CreateMLCEngine, InitProgressReport, MLCEngine } from "@mlc-ai/web-llm";
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  ArrowDown,
  ArrowUp,
  BookOpen,
  Check,
  ChevronDown,
  Copy,
  Cpu,
  FileText,
  Loader2,
  Mic,
  Paperclip,
  Radio,
  RefreshCw,
  Shield,
  Sparkles,
  Square,
  Zap,
} from 'lucide-react';
import { Suspense, useEffect, useRef, useState, useCallback } from 'react';
import { usePathname, useSearchParams, useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

// ============================================
// HELPERS
// ============================================

/**
 * Generate a dynamic conversation title from the first message
 * Creates a clean, readable title instead of just truncating
 */
function generateConversationTitle(message: string): string {
  // Clean up the message
  let title = message.trim();

  // Remove common prefixes that don't add meaning
  const prefixesToRemove = [
    /^(hi|hello|hey|good morning|good afternoon|good evening)[,!\s]*/i,
    /^(can you|could you|would you|please|i need|i want|i'd like)[,\s]*/i,
    /^(help me|assist me|tell me|show me|explain)[,\s]*/i,
  ];

  for (const prefix of prefixesToRemove) {
    title = title.replace(prefix, '');
  }

  // Capitalize first letter
  title = title.charAt(0).toUpperCase() + title.slice(1);

  // If the message is a question, keep the question mark
  const isQuestion = message.trim().endsWith('?');

  // Truncate to reasonable length (40 chars) at word boundary
  if (title.length > 40) {
    const truncated = title.substring(0, 40);
    const lastSpace = truncated.lastIndexOf(' ');
    if (lastSpace > 20) {
      title = truncated.substring(0, lastSpace) + '...';
    } else {
      title = truncated + '...';
    }
  }

  // If we stripped too much and title is too short, use a default approach
  if (title.length < 3) {
    title = message.trim().substring(0, 40);
    if (message.length > 40) title += '...';
  }

  return title;
}

// ============================================
// TYPES
// ============================================

interface ExtendedModel extends Model {
  isCloud?: boolean;
  provider?: 'openai' | 'local';
}

// Citation type is imported from '@/utils/citationParser'

interface Message {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Citation[];
}

// UI Conversation type (mapped from DB Thread)
interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  modelId?: string;
  createdAt: number;
  updatedAt: number;
  threadId: string; // Links to DB Thread
  conversationId: string; // Links to DB Conversation
}

// ============================================
// CONSTANTS
// ============================================

const AVAILABLE_MODELS: ExtendedModel[] = [
  {
    id: 'gpt-4o-mini',
    name: 'GPT-4O-MINI',
    description: 'OpenAI flagship mini model with superior reasoning capabilities',
    size: 'Cloud',
    parameters: 'Cloud API',
    ram: 'N/A',
    speed: 'Very Fast',
    accuracy: 95,
    features: ['Advanced Reasoning', 'Code Generation', 'Multimodal', 'Function Calling'],
    tags: ['openai', 'cloud', 'flagship'],
    isRecommended: true,
    isFeatured: true,
    isCloud: true,
    provider: 'openai',
    benchmarks: { reasoning: 94, coding: 92, math: 91, language: 96 }
  },
  {
    id: 'Llama-3.2-1B-Instruct-q4f32_1-MLC',
    name: 'LLAMA-3.2-1B',
    description: 'Ultra-efficient neural core for rapid transmissions',
    size: '1B',
    parameters: '1.2B',
    ram: '~2GB',
    speed: 'Very Fast',
    accuracy: 78,
    features: ['Text Synthesis', 'Query Processing', 'Compression'],
    tags: ['lightweight', 'fast', 'efficient'],
    isRecommended: true,
    benchmarks: { reasoning: 72, coding: 65, math: 70, language: 82 }
  },
  {
    id: 'Llama-3.2-3B-Instruct-q4f32_1-MLC',
    name: 'LLAMA-3.2-3B',
    description: 'Balanced neural architecture for complex reasoning',
    size: '3B',
    parameters: '3.2B',
    ram: '~4GB',
    speed: 'Fast',
    accuracy: 84,
    features: ['Deep Reasoning', 'Code Generation', 'Analysis'],
    tags: ['balanced', 'versatile', 'flagship'],
    isRecommended: true,
    isFeatured: true,
    benchmarks: { reasoning: 81, coding: 78, math: 79, language: 88 }
  },
  {
    id: 'gemma-2-2b-it-q4f16_1-MLC',
    name: 'GEMMA-2-2B',
    description: 'Google neural matrix with multilingual protocols',
    size: '2B',
    parameters: '2.6B',
    ram: '~3GB',
    speed: 'Fast',
    accuracy: 82,
    features: ['Multilingual', 'Code Analysis', 'Translation'],
    tags: ['multilingual', 'google', 'efficient'],
    benchmarks: { reasoning: 79, coding: 80, math: 76, language: 91 }
  },
  {
    id: 'Phi-3.5-mini-instruct-q4f16_1-MLC',
    name: 'PHI-3.5-MINI',
    description: 'Microsoft compact core optimized for instruction parsing',
    size: '3.8B',
    parameters: '3.8B',
    ram: '~4GB',
    speed: 'Medium',
    accuracy: 86,
    features: ['Instruction Parsing', 'Reasoning Engine', 'Code Synthesis'],
    tags: ['microsoft', 'instruction-tuned', 'reliable'],
    benchmarks: { reasoning: 85, coding: 83, math: 82, language: 87 }
  },
  {
    id: 'Qwen2-1.5B-Instruct-q4f16_1-MLC',
    name: 'QWEN2-1.5B',
    description: 'Alibaba neural core with bilingual transmission',
    size: '1.5B',
    parameters: '1.5B',
    ram: '~2GB',
    speed: 'Very Fast',
    accuracy: 80,
    features: ['Bilingual', 'Fast Processing', 'Query Response'],
    tags: ['lightweight', 'bilingual', 'alibaba'],
    isRecommended: true,
    benchmarks: { reasoning: 76, coding: 71, math: 74, language: 86 }
  },
];

const DEFAULT_SETTINGS: ChatSettings = {
  temperature: 0.7,
  maxTokens: 2048,
  topP: 0.9,
  frequencyPenalty: 0,
  presencePenalty: 0,
  systemPrompt: 'You are an advanced AI assistant operating within the Terminal Observatory. Provide precise, well-structured responses.',
  systemPromptTemplate: 'default',
  streamResponses: true,
  autoSave: true,
  showTimestamps: true,
  showThinking: false,
  markdownRendering: true,
  theme: 'system',
  fontSize: 'medium',
  compactMode: false,
  showAvatars: true,
  soundEnabled: true,
  desktopNotifications: false,
  dataRetention: 30,
  shareAnalytics: false,
};

// Database-backed storage - no more localStorage for conversations

const STARTER_PROMPTS = [
  {
    icon: BookOpen,
    title: 'Summarize Research',
    prompt: 'Summarize the key findings from the recent papers on RAG optimization',
  },
  {
    icon: Zap,
    title: 'Compare Embeddings',
    prompt: 'Compare BAAI/bge-large vs OpenAI embeddings for semantic search',
  },
  {
    icon: FileText,
    title: 'Analyze Document',
    prompt: 'Analyze the methodology section of the uploaded paper',
  },
  {
    icon: Sparkles,
    title: 'Generate Ideas',
    prompt: 'Suggest improvements for our current retrieval pipeline',
  },
];

// ============================================
// MESSAGE COMPONENT
// ============================================

function ChatMessage({
  message,
  index,
  modelName,
  isTyping,
  onRetry,
  onCitationClick,
}: {
  message: Message;
  index: number;
  modelName?: string;
  isTyping?: boolean;
  onRetry?: () => void;
  onCitationClick?: (citations: Citation[], clickedCitation: Citation) => void;
}) {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);
  const timestamp = message.timestamp
    ? new Date(message.timestamp).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })
    : '--:--';

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{
        duration: 0.4,
        delay: index * 0.03,
        ease: [0.25, 0.46, 0.45, 0.94]
      }}
      className={cn('group relative mb-6', isUser ? 'ml-12 sm:ml-16' : 'mr-12 sm:mr-16')}
    >
      {/* Transmission Line with glow effect */}
      <div
        className={cn(
          'absolute top-0 h-full w-[2px] transition-all duration-300',
          isUser
            ? 'right-0 bg-gradient-to-b from-[var(--amber-gold)] via-[var(--amber-gold)]/50 to-transparent group-hover:shadow-[0_0_8px_var(--amber-gold)]'
            : 'left-0 bg-gradient-to-b from-[var(--phosphor-green)] via-[var(--phosphor-green)]/50 to-transparent group-hover:shadow-[0_0_8px_var(--phosphor-green)]'
        )}
        style={{ opacity: 0.5 }}
      />

      {/* Message Header */}
      <div
        className={cn(
          'flex items-center gap-3 mb-2 text-[10px]',
          isUser ? 'justify-end pr-4' : 'pl-4'
        )}
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {!isUser && (
          <>
            <div className="flex items-center gap-2">
              <div className={cn(
                "w-1.5 h-1.5 rounded-full bg-[var(--phosphor-green)]",
                isTyping ? "animate-pulse" : "signal-active"
              )} />
              <span className="text-[var(--phosphor-green)] uppercase tracking-wider">
                {isTyping ? 'STREAMING' : 'RESPONSE'}
              </span>
            </div>
            {modelName && (
              <span className="text-[var(--terminal-text-muted)]">[{modelName}]</span>
            )}
          </>
        )}
        {isUser && (
          <span className="text-[var(--amber-gold)] uppercase tracking-wider">
            QUERY
          </span>
        )}
        <span className="text-[var(--terminal-text-muted)]">{timestamp}</span>

        {/* Quick Actions - visible on hover */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
          <button
            onClick={handleCopy}
            className={cn(
              "p-1 rounded hover:bg-[var(--terminal-elevated)] transition-all",
              copied ? "text-[var(--phosphor-green)]" : "text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)]"
            )}
            title={copied ? "Copied!" : "Copy message"}
          >
            {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
          </button>
          {isUser && onRetry && (
            <button
              onClick={onRetry}
              className="p-1 rounded hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)] transition-all"
              title="Retry"
            >
              <RefreshCw className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* Message Content */}
      <div
        className={cn(
          'relative rounded-lg overflow-hidden',
          isUser
            ? 'bg-gradient-to-br from-[#1a1510] to-[var(--terminal-bg)] border border-[#3d2f1a] mr-4'
            : 'bg-[var(--terminal-surface)] border border-[var(--terminal-border)] ml-4'
        )}
      >
        <div className="absolute inset-0 holo-shimmer opacity-30" />

        <div className="relative p-4">
          {isTyping && !message.content ? (
            <div
              className="flex items-center gap-3 text-[var(--phosphor-green)] text-sm"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              <div className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-[var(--phosphor-green)] animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 rounded-full bg-[var(--phosphor-green)] animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 rounded-full bg-[var(--phosphor-green)] animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
              <span className="opacity-70">Generating response...</span>
            </div>
          ) : (
            <div
              className={cn(
                'text-sm leading-relaxed',
                isUser ? 'text-[#e8d5b5]' : 'text-[var(--terminal-text)]'
              )}
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {isUser ? (
                <p className="whitespace-pre-wrap">{message.content}</p>
              ) : (
                <CitationRenderer
                  content={message.content}
                  citations={message.citations as Citation[]}
                  onCitationClick={(citation) => {
                    if (onCitationClick && message.citations) {
                      onCitationClick(message.citations as Citation[], citation);
                    }
                  }}
                />
              )}
            </div>
          )}
        </div>

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="border-t border-[var(--terminal-border)] p-3 bg-[var(--terminal-bg)]">
            <div
              className="text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider mb-2"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              SOURCES ({message.citations.length})
            </div>
            <div className="flex flex-wrap gap-2">
              {message.citations.map((citation, idx) => (
                <button
                  key={idx}
                  className="flex items-center gap-2 px-2 py-1.5 rounded bg-[var(--terminal-surface)] border border-[var(--terminal-border)] hover:border-[var(--phosphor-green)]/30 text-[10px] transition-colors"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <FileText className="w-3 h-3 text-[var(--phosphor-green)]" />
                  <span className="text-[var(--terminal-text)] truncate max-w-[150px]">
                    {citation.title}
                  </span>
                  <span className="text-[var(--phosphor-green)]">
                    {Math.round(citation.score * 100)}%
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

// ============================================
// MODEL SELECTOR
// ============================================

function ModelSelector({
  models,
  selectedModelId,
  onModelChange,
  isLoading,
}: {
  models: ExtendedModel[];
  selectedModelId?: string;
  onModelChange: (id: string) => void;
  isLoading?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const selectedModel = models.find((m) => m.id === selectedModelId);

  return (
    <div className="relative">
      <button
        onClick={() => !isLoading && setIsOpen(!isOpen)}
        disabled={isLoading}
        className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs transition-all',
          'bg-[var(--terminal-surface)] border-[var(--terminal-border)]',
          'hover:border-[var(--phosphor-green)]/30',
          isLoading && 'opacity-50 cursor-not-allowed'
        )}
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        <Cpu className="w-3.5 h-3.5 text-[var(--phosphor-green)]" />
        <span className="text-[var(--terminal-text)]">
          {selectedModel?.name || 'SELECT MODEL'}
        </span>
        {selectedModel?.isCloud && (
          <span className="px-1 py-0.5 rounded bg-[var(--amber-gold)]/20 text-[var(--amber-gold)] text-[8px] uppercase">
            Cloud
          </span>
        )}
        <ChevronDown
          className={cn(
            'w-3 h-3 text-[var(--terminal-text-muted)] transition-transform',
            isOpen && 'rotate-180'
          )}
        />
      </button>

      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40"
              onClick={() => setIsOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="absolute bottom-full left-0 mb-2 w-80 terminal-window z-50"
            >
              <div className="p-2 max-h-80 overflow-y-auto terminal-scrollbar">
                {models.map((model) => (
                  <button
                    key={model.id}
                    onClick={() => {
                      onModelChange(model.id);
                      setIsOpen(false);
                    }}
                    className={cn(
                      'w-full flex items-start gap-3 px-3 py-2.5 rounded text-left transition-colors',
                      model.id === selectedModelId
                        ? 'bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/30'
                        : 'hover:bg-[var(--terminal-elevated)]'
                    )}
                  >
                    <Cpu
                      className={cn(
                        'w-4 h-4 mt-0.5',
                        model.id === selectedModelId
                          ? 'text-[var(--phosphor-green)]'
                          : 'text-[var(--terminal-text-muted)]'
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            'text-xs font-medium',
                            model.id === selectedModelId
                              ? 'text-[var(--phosphor-green)]'
                              : 'text-[var(--terminal-text)]'
                          )}
                          style={{ fontFamily: "'JetBrains Mono', monospace" }}
                        >
                          {model.name}
                        </span>
                        {model.isCloud && (
                          <span className="px-1.5 py-0.5 rounded bg-[var(--amber-gold)]/20 text-[var(--amber-gold)] text-[8px] uppercase">
                            Cloud
                          </span>
                        )}
                        {model.isFeatured && (
                          <span className="px-1.5 py-0.5 rounded bg-[var(--phosphor-green)]/20 text-[var(--phosphor-green)] text-[8px] uppercase">
                            Featured
                          </span>
                        )}
                      </div>
                      <p
                        className="text-[10px] text-[var(--terminal-text-muted)] mt-0.5"
                        style={{ fontFamily: "'JetBrains Mono', monospace" }}
                      >
                        {model.description}
                      </p>
                      <div
                        className="flex items-center gap-3 mt-1 text-[10px] text-[var(--terminal-text-dim)]"
                        style={{ fontFamily: "'JetBrains Mono', monospace" }}
                      >
                        <span>PARAMS: {model.parameters}</span>
                        <span>RAM: {model.ram}</span>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

// ============================================
// CHAT INPUT
// ============================================

function ChatInput({
  value,
  onChange,
  onSubmit,
  onStop,
  isLoading,
  isModelLoading,
  selectedModel,
  models,
  onModelChange,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  isLoading: boolean;
  isModelLoading: boolean;
  selectedModel?: string;
  models: ExtendedModel[];
  onModelChange: (id: string) => void;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isFocused, setIsFocused] = useState(false);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && !isModelLoading && value.trim() && selectedModel) {
        onSubmit();
      }
    }
  };

  const isDisabled = !selectedModel || isModelLoading;
  const charCount = value.length;
  const maxChars = 4000;
  const isNearLimit = charCount > maxChars * 0.8;

  return (
    <div className="border-t border-[var(--terminal-border)] bg-[var(--terminal-bg)]/95 backdrop-blur-xl">
      <div className="max-w-4xl mx-auto p-4">
        <motion.div
          className={cn(
            "terminal-window p-3 transition-all duration-300",
            isFocused && "ring-1 ring-[var(--phosphor-green)]/30 shadow-[0_0_20px_rgba(0,255,159,0.1)]"
          )}
          animate={{
            borderColor: isFocused ? 'rgba(0, 255, 159, 0.3)' : 'var(--terminal-border)'
          }}
        >
          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={selectedModel ? "Type your message..." : "Select a model to start..."}
            rows={1}
            className="w-full bg-transparent text-[var(--terminal-text)] text-sm resize-none outline-none"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              minHeight: '24px',
              maxHeight: '200px',
            }}
            disabled={isDisabled}
          />

          {/* Actions Bar */}
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-[var(--terminal-border)]">
            <div className="flex items-center gap-2">
              <ModelSelector
                models={models}
                selectedModelId={selectedModel}
                onModelChange={onModelChange}
                isLoading={isModelLoading}
              />
              <button
                className="p-2 rounded-lg hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)] transition-colors"
                title="Attach file"
              >
                <Paperclip className="w-4 h-4" />
              </button>
              <button
                className="p-2 rounded-lg hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)] transition-colors"
                title="Voice input"
              >
                <Mic className="w-4 h-4" />
              </button>
            </div>

            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "text-[10px] transition-colors",
                  isNearLimit ? "text-[var(--amber-gold)]" : "text-[var(--terminal-text-muted)]"
                )}
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                {charCount.toLocaleString()}{isNearLimit && ` / ${maxChars.toLocaleString()}`}
              </span>
              {isLoading ? (
                <button
                  onClick={onStop}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--error-red)] text-white text-xs font-medium hover:bg-[var(--error-red)]/80 transition-colors"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <Square className="w-3.5 h-3.5" />
                  STOP
                </button>
              ) : (
                <button
                  onClick={onSubmit}
                  disabled={!value.trim() || isDisabled}
                  className={cn(
                    'flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all',
                    value.trim() && !isDisabled
                      ? 'bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_20px_var(--phosphor-green-glow)]'
                      : 'bg-[var(--terminal-elevated)] text-[var(--terminal-text-muted)] cursor-not-allowed'
                  )}
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <ArrowUp className="w-3.5 h-3.5" />
                  SEND
                </button>
              )}
            </div>
          </div>
        </motion.div>

        {/* Keyboard Hint - fades when focused */}
        <motion.div
          initial={{ opacity: 0.7 }}
          animate={{ opacity: isFocused ? 0.4 : 0.7 }}
          className="flex items-center justify-center gap-4 mt-2 text-[10px] text-[var(--terminal-text-muted)]"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          <span>
            <kbd className="px-1.5 py-0.5 rounded bg-[var(--terminal-surface)] border border-[var(--terminal-border)]">
              Enter
            </kbd>{' '}
            send
          </span>
          <span>
            <kbd className="px-1.5 py-0.5 rounded bg-[var(--terminal-surface)] border border-[var(--terminal-border)]">
              Shift+Enter
            </kbd>{' '}
            new line
          </span>
          <span className="hidden sm:inline">
            <kbd className="px-1.5 py-0.5 rounded bg-[var(--terminal-surface)] border border-[var(--terminal-border)]">
              /
            </kbd>{' '}
            commands
          </span>
        </motion.div>
      </div>
    </div>
  );
}

// ============================================
// WELCOME STATE
// ============================================

function WelcomeState({
  onPromptSelect,
  selectedModel,
}: {
  onPromptSelect: (prompt: string) => void;
  selectedModel?: string;
}) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-center max-w-2xl"
      >
        {/* Logo */}
        <div className="relative w-24 h-24 mx-auto mb-8">
          <div className="absolute inset-0 rounded-full bg-[var(--phosphor-green)]/10 animate-pulse" />
          <div className="absolute inset-2 rounded-full border-2 border-[var(--phosphor-green)]/30 flex items-center justify-center">
            <Sparkles className="w-10 h-10 text-[var(--phosphor-green)]" />
          </div>
        </div>

        {/* Title */}
        <h1
          className="text-2xl text-[var(--phosphor-green)] mb-3"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {selectedModel ? 'NEURAL LINK ESTABLISHED' : 'AWAITING MODEL SELECTION'}
        </h1>
        <p
          className="text-sm text-[var(--terminal-text-muted)] mb-8"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {selectedModel
            ? 'Your GenAI research companion is ready. Ask questions about your documents, explore research papers, and generate insights.'
            : 'Select a neural core from the input bar below to initialize the interface.'}
        </p>

        {/* Starter Prompts */}
        {selectedModel && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {STARTER_PROMPTS.map((item, idx) => (
                <motion.button
                  key={idx}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 + idx * 0.1 }}
                  onClick={() => onPromptSelect(item.prompt)}
                  className="flex items-start gap-3 p-4 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] hover:border-[var(--phosphor-green)]/30 hover:bg-[var(--terminal-elevated)] text-left transition-all group"
                >
                  <div className="p-2 rounded-lg bg-[var(--phosphor-green)]/10 text-[var(--phosphor-green)] group-hover:bg-[var(--phosphor-green)]/20 transition-colors">
                    <item.icon className="w-4 h-4" />
                  </div>
                  <div>
                    <h3
                      className="text-xs text-[var(--terminal-text)] mb-1"
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}
                    >
                      {item.title}
                    </h3>
                    <p
                      className="text-[10px] text-[var(--terminal-text-muted)] line-clamp-2"
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}
                    >
                      {item.prompt}
                    </p>
                  </div>
                </motion.button>
              ))}
            </div>

            {/* Features */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="mt-8 grid grid-cols-2 sm:grid-cols-4 gap-3"
            >
              {[
                { icon: Zap, label: 'RAPID PROCESSING' },
                { icon: Shield, label: 'SECURE' },
                { icon: Cpu, label: 'RAG ENABLED' },
                { icon: Activity, label: 'REAL-TIME' },
              ].map((item, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 p-2 rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)]"
                >
                  <item.icon className="w-3 h-3 text-[var(--phosphor-green)]" />
                  <span
                    className="text-[10px] text-[var(--terminal-text-muted)]"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    {item.label}
                  </span>
                </div>
              ))}
            </motion.div>
          </>
        )}
      </motion.div>
    </div>
  );
}

// ============================================
// MODEL LOADING PROGRESS
// ============================================

function ModelLoadingProgress({
  progress,
  progressVal,
}: {
  progress: string;
  progressVal: number;
}) {
  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      className="border-b border-[var(--terminal-border)] overflow-hidden bg-[var(--terminal-bg)]"
    >
      <div className="px-4 py-3 max-w-4xl mx-auto">
        <div className="flex items-center gap-4">
          <div className="relative">
            <Radio className="w-5 h-5 text-[var(--phosphor-green)] animate-pulse" />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-2 h-2 rounded-full bg-[var(--phosphor-green)] animate-ping" />
            </div>
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1">
              <span
                className="text-xs text-[var(--phosphor-green)]"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                ESTABLISHING NEURAL LINK...
              </span>
              <span
                className="text-xs text-[var(--terminal-text-muted)]"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                {Math.round(progressVal * 100)}%
              </span>
            </div>
            <div className="h-1 bg-[var(--terminal-border)] rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-[var(--phosphor-green)] to-[var(--phosphor-green-dim)]"
                initial={{ width: 0 }}
                animate={{ width: progressVal * 100 + '%' }}
                transition={{ duration: 0.3 }}
              />
            </div>
            <p
              className="text-[10px] text-[var(--terminal-text-muted)] mt-1 truncate"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {progress}
            </p>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

// ============================================
// MAIN PAGE COMPONENT
// ============================================

function ChatPageContent() {
  // Core state
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState<string>('');

  // Database state
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [dbConversation, setDbConversation] = useState<DBConversation | null>(null);
  const [activeThread, setActiveThread] = useState<Thread | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [initError, setInitError] = useState<string | null>(null);

  // Loading states
  const [isLoading, setIsLoading] = useState(false);
  const [isModelLoading, setIsModelLoading] = useState(false);
  const [progress, setProgress] = useState('');
  const [progressVal, setProgressVal] = useState(0);

  // Settings
  const [settings] = useState<ChatSettings>(DEFAULT_SETTINGS);

  // Refs
  const engineRef = useRef<MLCEngine | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isHydratedRef = useRef(false);
  const hasRestoredThreadRef = useRef(false);

  // Scroll state
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Citation panel state
  const [isCitationPanelOpen, setIsCitationPanelOpen] = useState(false);
  const [citationPanelCitations, setCitationPanelCitations] = useState<Citation[]>([]);
  const [activeCitationId, setActiveCitationId] = useState<string | undefined>(undefined);

  // Auth
  const { isAuthenticated, token } = useAuthStore();

  // Get currentThreadId and setCurrentThread from chat store to sync with sidebar
  const currentThreadIdFromStore = useChatStore((state) => state.currentThreadId);
  const setCurrentThread = useChatStore((state) => state.setCurrentThread);
  const storeMessages = useChatStore((state) => state.messages);

  // Navigation detection
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();

  // Reset refs when user changes (logout/login)
  useEffect(() => {
    if (!isAuthenticated) {
      hasRestoredThreadRef.current = false;
      isHydratedRef.current = false;
    }
  }, [isAuthenticated]);

  // Handle thread switching from URL query param or sessionStorage (when navigating from sidebar)
  // This runs whenever we're on /chat and checks for pending thread switch
  useEffect(() => {
    if (conversations.length === 0 || isInitializing) {
      return;
    }

    // Check URL query param first (most reliable), then sessionStorage
    const threadFromUrl = searchParams.get('thread');
    const threadFromStorage = sessionStorage.getItem('activeThreadId');
    const targetThreadId = threadFromUrl || threadFromStorage;

    if (targetThreadId) {
      console.log('[Chat] Thread switch requested:', targetThreadId, 'source:', threadFromUrl ? 'URL' : 'sessionStorage');
      const targetConv = conversations.find(c => c.id === targetThreadId);

      if (targetConv) {
        if (targetConv.id !== activeConversationId) {
          setActiveConversationId(targetConv.id);
          setMessages(targetConv.messages);
          // Also update the Zustand store so sidebar highlights correctly
          setCurrentThread(targetConv.id);
          console.log('[Chat] Switched to thread:', targetConv.title);
        }
      } else {
        console.log('[Chat] Thread not found in conversations:', targetThreadId);
      }

      // Clear sessionStorage (URL param stays for bookmarking/sharing)
      sessionStorage.removeItem('activeThreadId');
    }
  }, [searchParams, conversations, isInitializing, activeConversationId, setCurrentThread]);

  // Sync with Zustand store's currentThreadId (triggered by sidebar clicks via useChatPersistence)
  // This ensures the chat page updates when sidebar selection changes the store
  useEffect(() => {
    if (!currentThreadIdFromStore || isInitializing || conversations.length === 0) {
      return;
    }

    // Only update if the store's thread is different from our local state
    if (currentThreadIdFromStore !== activeConversationId) {
      console.log('[Chat] Store thread changed:', currentThreadIdFromStore, '(local:', activeConversationId, ')');

      // Try to find the thread in local conversations first
      const targetConv = conversations.find(c => c.id === currentThreadIdFromStore);

      if (targetConv) {
        console.log('[Chat] Found thread in local state, syncing:', targetConv.title);
        setActiveConversationId(targetConv.id);
        setMessages(targetConv.messages);
      } else {
        // Thread not in local conversations, try to load from store messages
        const messagesFromStore = storeMessages[currentThreadIdFromStore];
        if (messagesFromStore && messagesFromStore.length > 0) {
          console.log('[Chat] Loading messages from store for thread:', currentThreadIdFromStore);
          setActiveConversationId(currentThreadIdFromStore);
          // Map store messages to UI format inline
          setMessages(messagesFromStore.map((dbMsg) => ({
            id: dbMsg.id,
            role: dbMsg.role === MessageRole.USER ? 'user' as const : 'assistant' as const,
            content: dbMsg.content,
            timestamp: new Date(dbMsg.created_at).getTime(),
            citations: dbMsg.citations?.map((c) => ({
              documentId: c.document_id,
              title: c.document_title || 'Unknown Document',
              score: c.score || 0,
            })),
          })));
        } else {
          // Thread exists but no messages yet - still switch to it
          console.log('[Chat] Switching to thread with no messages:', currentThreadIdFromStore);
          setActiveConversationId(currentThreadIdFromStore);
          setMessages([]);
        }
      }
    }
  }, [currentThreadIdFromStore, conversations, isInitializing, activeConversationId, storeMessages]);

  // Map DB messages to UI messages
  const mapDbMessageToUiMessage = useCallback((dbMsg: DBChatMessage): Message => {
    return {
      id: dbMsg.id,
      role: dbMsg.role === MessageRole.USER ? 'user' : 'assistant',
      content: dbMsg.content,
      timestamp: new Date(dbMsg.created_at).getTime(),
      citations: dbMsg.citations?.map((c) => ({
        documentId: c.document_id,
        title: c.document_title || 'Unknown Document',
        score: c.score || 0,
      })),
    };
  }, []);

  // Load threads and messages from database
  const loadThreadsFromDb = useCallback(async (conversationId: string, isRetry = false): Promise<boolean> => {
    try {
      console.log('[Chat] Loading threads from database for conversation:', conversationId);
      const threadResponse = await workspaceService.listThreads(conversationId, { limit: 50 });

      // Map threads to UI conversations
      const uiConversations: Conversation[] = await Promise.all(
        threadResponse.threads.map(async (thread) => {
          // Load messages for each thread
          const msgResponse = await workspaceService.listMessages(thread.id, { limit: 100 });
          const uiMessages = msgResponse.messages.map(mapDbMessageToUiMessage);

          return {
            id: thread.id,
            title: thread.title || 'New Chat',
            messages: uiMessages,
            createdAt: new Date(thread.created_at).getTime(),
            updatedAt: new Date(thread.updated_at).getTime(),
            threadId: thread.id,
            conversationId: conversationId,
          };
        })
      );

      setConversations(uiConversations);
      console.log('[Chat] Loaded', uiConversations.length, 'threads from database');

      // Restore active thread - check sessionStorage first, then use first conversation
      if (uiConversations.length > 0) {
        // Only set state if we haven't already done so
        // This prevents React Strict Mode double-execution from overwriting correct state
        if (hasRestoredThreadRef.current) {
          console.log('[Chat] Skipping thread restore (already done, preventing Strict Mode duplicate)');
          return true;
        }

        let selectedConv = uiConversations[0];
        const savedThreadId = sessionStorage.getItem('activeThreadId');

        if (savedThreadId) {
          const savedConv = uiConversations.find(c => c.id === savedThreadId);
          if (savedConv) {
            selectedConv = savedConv;
            console.log('[Chat] Restored thread from sessionStorage:', savedConv.title);
          }
          // Clear the sessionStorage after using it
          sessionStorage.removeItem('activeThreadId');
        }

        hasRestoredThreadRef.current = true;
        setActiveConversationId(selectedConv.id);
        setMessages(selectedConv.messages);
        // Sync with Zustand store for sidebar highlighting
        setCurrentThread(selectedConv.id);
        console.log('[Chat] Active thread:', selectedConv.title);
      }
      return true;
    } catch (error: any) {
      console.error('[Chat] Failed to load threads from database:', error);

      // Handle 404 - conversation not found (stale data)
      if (error?.response?.status === 404 || error?.status_code === 404) {
        console.warn('[Chat] Conversation not found (404) - clearing stale data');
        // Clear stale localStorage data
        if (typeof window !== 'undefined') {
          localStorage.removeItem('default-workspace-id');
          localStorage.removeItem('default-conversation-id');
        }
        return false; // Signal to caller to retry with fresh data
      }

      throw error;
    }
  }, [mapDbMessageToUiMessage, setCurrentThread]);

  // Initialize workspace and conversation from database
  useEffect(() => {
    const initializeFromDb = async () => {
      if (!isAuthenticated || !token) {
        console.log('[Chat] Not authenticated, skipping database initialization');
        setIsInitializing(false);
        return;
      }

      try {
        console.log('[Chat] Initializing from database...');
        setIsInitializing(true);
        setInitError(null);

        // Get or create default workspace
        const ws = await workspaceService.getOrCreateDefaultWorkspace();
        setWorkspace(ws);
        console.log('[Chat] Workspace:', ws.name);

        // Get or create default conversation
        const conv = await workspaceService.getOrCreateDefaultConversation(ws.id);
        setDbConversation(conv);
        console.log('[Chat] DB Conversation:', conv.title);

        // Load threads - handle stale conversation data
        const loadSuccess = await loadThreadsFromDb(conv.id);

        // If load failed due to 404, create fresh conversation
        if (!loadSuccess) {
          console.log('[Chat] Retrying with fresh conversation...');
          const freshConv = await workspaceService.createConversation({
            workspace_id: ws.id,
            title: 'New Chat',
            description: 'A new conversation',
          });
          setDbConversation(freshConv);
          console.log('[Chat] Created fresh conversation:', freshConv.title);

          // Try loading threads again (should be empty for new conversation)
          await loadThreadsFromDb(freshConv.id);
        }

        isHydratedRef.current = true;
        console.log('[Chat] Database initialization complete');
      } catch (error: any) {
        console.error('[Chat] Failed to initialize from database:', error);

        // Handle 404 by clearing stale data and retrying once
        if (error?.response?.status === 404) {
          console.warn('[Chat] Stale data detected, clearing and retrying...');
          if (typeof window !== 'undefined') {
            localStorage.removeItem('default-workspace-id');
            localStorage.removeItem('default-conversation-id');
          }
          // Retry once after clearing stale data
          try {
            const ws = await workspaceService.getOrCreateDefaultWorkspace();
            setWorkspace(ws);
            const conv = await workspaceService.createConversation({
              workspace_id: ws.id,
              title: 'New Chat',
              description: 'A new conversation',
            });
            setDbConversation(conv);
            setConversations([]);
            setMessages([]);
            console.log('[Chat] Created fresh workspace and conversation');
            isHydratedRef.current = true;
            setIsInitializing(false);
            return;
          } catch (retryError) {
            console.error('[Chat] Retry failed:', retryError);
            setInitError('Failed to create new chat session. Please refresh the page.');
            setIsInitializing(false);
            return;
          }
        }

        setInitError(error instanceof Error ? error.message : 'Failed to load chat data');
      } finally {
        setIsInitializing(false);
      }
    };

    initializeFromDb();
  }, [isAuthenticated, token, loadThreadsFromDb]);

  // Load messages when active conversation changes
  useEffect(() => {
    if (activeConversationId) {
      const conv = conversations.find((c) => c.id === activeConversationId);
      if (conv) {
        setMessages(conv.messages);
      }
    }
  }, [activeConversationId, conversations]);

  // Auto-scroll when new messages arrive
  useEffect(() => {
    if (!showScrollButton) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, showScrollButton]);

  // Handle scroll to detect if user scrolled up
  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const { scrollTop, scrollHeight, clientHeight } = container;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    setShowScrollButton(!isNearBottom && messages.length > 0);
  }, [messages.length]);

  // Scroll to bottom function
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    setShowScrollButton(false);
  }, []);

  // Model initialization
  const initProgressCallback = (report: InitProgressReport) => {
    setProgress(report.text);
    setProgressVal(report.progress);
  };

  const loadModel = async (modelId: string) => {
    const model = AVAILABLE_MODELS.find((m) => m.id === modelId);

    // Skip WebLLM loading for cloud models
    if (model?.isCloud) {
      setProgress('Cloud model ready - no local loading required');
      setProgressVal(1);
      return;
    }

    setIsModelLoading(true);
    try {
      if (!engineRef.current) {
        engineRef.current = await CreateMLCEngine(modelId, { initProgressCallback });
      } else {
        await engineRef.current.reload(modelId);
      }
    } catch (err) {
      console.error('Failed to load model:', err);
    } finally {
      setIsModelLoading(false);
    }
  };

  // Model change handler
  const handleModelChange = async (modelId: string) => {
    setSelectedModel(modelId);
    await loadModel(modelId);
  };

  // Send message
  const handleSubmit = async () => {
    if (!input.trim() || isLoading || isModelLoading || !selectedModel) return;

    const model = AVAILABLE_MODELS.find((m) => m.id === selectedModel);
    const isCloudModel = model?.isCloud;

    // For local models, require engine to be initialized
    if (!isCloudModel && !engineRef.current) {
      console.error('Engine not initialized');
      return;
    }

    const userMessage: Message = {
      role: 'user',
      content: input.trim(),
      timestamp: Date.now(),
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);

    // Create new thread if needed (when no active conversation)
    let currentConversationId = activeConversationId;
    let currentThreadId = activeConversationId; // In our mapping, conversation ID = thread ID

    if (!currentConversationId && dbConversation) {
      try {
        // Create new thread in database with dynamic title
        const dynamicTitle = generateConversationTitle(input);
        console.log('[Chat] Creating new thread in database with title:', dynamicTitle);
        const newThread = await workspaceService.createThread({
          conversation_id: dbConversation.id,
          title: dynamicTitle,
          initial_message: input.trim(),
        });

        currentConversationId = newThread.id;
        currentThreadId = newThread.id;

        const newConv: Conversation = {
          id: newThread.id,
          title: newThread.title || dynamicTitle,
          messages: newMessages,
          modelId: selectedModel,
          createdAt: Date.now(),
          updatedAt: Date.now(),
          threadId: newThread.id,
          conversationId: dbConversation.id,
        };

        setConversations((prev) => [newConv, ...prev]);
        setActiveConversationId(newConv.id);
        setActiveThread(newThread);
        console.log('[Chat] Created new thread:', newThread.id);
      } catch (error) {
        console.error('[Chat] Failed to create thread:', error);
        setIsLoading(false);
        return;
      }
    }

    // Save user message to database
    if (currentThreadId && isAuthenticated) {
      try {
        await workspaceService.createMessage({
          thread_id: currentThreadId,
          content: input.trim(),
          role: MessageRole.USER,
        });
        console.log('[Chat] Saved user message to database');
      } catch (error) {
        console.error('[Chat] Failed to save user message:', error);
      }
    }

    try {
      let assistantMessage = '';

      if (isCloudModel) {
        // Use backend API for cloud models (GPT-4o mini via Azure OpenAI)
        const data = await apiClient.post<{
          message: { role: string; content: string };
          model: string;
          usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
          finish_reason: string;
          timestamp: string;
          rag_enabled: boolean;
          retrieved_contexts?: Array<{
            document_id: string;
            title: string;
            content: string;
            score: number;
            source?: string;
          }>;
        }>('/chat/completions', {
          messages: newMessages.map((m) => ({ role: m.role, content: m.content })),
          model: selectedModel,
          temperature: settings.temperature,
          max_tokens: settings.maxTokens,
          system_prompt: settings.systemPrompt,
          use_rag: true,
          max_context_docs: 5,
        });
        assistantMessage = data.message?.content || 'No response from the model.';

        // Extract citations from retrieved contexts
        const citations: Citation[] = (data.retrieved_contexts || []).map((ctx: any) => ({
          documentId: ctx.document_id,
          title: ctx.title,
          score: ctx.score,
        }));

        // Save assistant message to database
        if (currentThreadId && isAuthenticated) {
          try {
            await workspaceService.createMessage({
              thread_id: currentThreadId,
              content: assistantMessage,
              role: MessageRole.ASSISTANT,
            });
            console.log('[Chat] Saved assistant message to database');
          } catch (error) {
            console.error('[Chat] Failed to save assistant message:', error);
          }
        }

        // Update messages with assistant response
        const finalMessages: Message[] = [
          ...newMessages,
          {
            role: 'assistant',
            content: assistantMessage,
            timestamp: Date.now(),
            citations: citations.length > 0 ? citations : undefined,
          },
        ];

        setMessages(finalMessages);

        // Update conversation
        setConversations((prev) =>
          prev.map((conv) =>
            conv.id === currentConversationId
              ? { ...conv, messages: finalMessages, updatedAt: Date.now() }
              : conv
          )
        );
      } else {
        // Use local WebLLM engine for browser-based models
        const response = await engineRef.current!.chat.completions.create({
          messages: [
            { role: 'system', content: settings.systemPrompt },
            ...newMessages.map((m) => ({ role: m.role, content: m.content })),
          ],
          temperature: settings.temperature,
          max_tokens: settings.maxTokens,
          stream: true,
        });

        // Handle streaming response
        for await (const chunk of response) {
          const delta = chunk.choices[0]?.delta?.content || '';
          assistantMessage += delta;
          setMessages([
            ...newMessages,
            {
              role: 'assistant',
              content: assistantMessage,
              timestamp: Date.now(),
            },
          ]);
        }

        // Save assistant message to database (for local models too)
        if (currentThreadId && isAuthenticated) {
          try {
            await workspaceService.createMessage({
              thread_id: currentThreadId,
              content: assistantMessage,
              role: MessageRole.ASSISTANT,
            });
            console.log('[Chat] Saved local model response to database');
          } catch (error) {
            console.error('[Chat] Failed to save assistant message:', error);
          }
        }

        const finalMessages: Message[] = [
          ...newMessages,
          {
            role: 'assistant',
            content: assistantMessage,
            timestamp: Date.now(),
          },
        ];

        setMessages(finalMessages);

        // Update conversation
        setConversations((prev) =>
          prev.map((conv) =>
            conv.id === currentConversationId
              ? { ...conv, messages: finalMessages, updatedAt: Date.now() }
              : conv
          )
        );
      }
    } catch (err) {
      console.error('Failed to send message:', err);
      const errorMessage = 'Error: ' + (err instanceof Error ? err.message : 'Failed to get response');

      setMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: errorMessage,
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStop = () => {
    setIsLoading(false);
  };

  const handlePromptSelect = (prompt: string) => {
    setInput(prompt);
  };

  const currentModel = AVAILABLE_MODELS.find((m) => m.id === selectedModel);

  return (
    <div className="flex flex-col h-full">
      {/* Model Loading Progress */}
      <AnimatePresence>
        {isModelLoading && (
          <ModelLoadingProgress progress={progress} progressVal={progressVal} />
        )}
      </AnimatePresence>

      {/* Messages Area */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto terminal-scrollbar relative"
      >
        {/* Scroll to bottom button */}
        <AnimatePresence>
          {showScrollButton && (
            <motion.button
              initial={{ opacity: 0, y: 10, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.9 }}
              onClick={scrollToBottom}
              className="fixed bottom-32 right-8 z-10 flex items-center gap-2 px-3 py-2 rounded-full bg-[var(--phosphor-green)] text-[var(--terminal-bg)] text-xs font-medium shadow-lg hover:shadow-[0_0_20px_var(--phosphor-green-glow)] transition-all"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              <ArrowDown className="w-4 h-4" />
              <span className="hidden sm:inline">New messages</span>
            </motion.button>
          )}
        </AnimatePresence>
        {/* Authentication Required State */}
        {!isAuthenticated ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center max-w-md"
            >
              <div className="relative w-20 h-20 mx-auto mb-6">
                <div className="absolute inset-0 rounded-full bg-[var(--amber-gold)]/10" />
                <div className="absolute inset-2 rounded-full border-2 border-[var(--amber-gold)]/30 flex items-center justify-center">
                  <Shield className="w-8 h-8 text-[var(--amber-gold)]" />
                </div>
              </div>
              <h2
                className="text-xl text-[var(--amber-gold)] mb-3"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                AUTHENTICATION REQUIRED
              </h2>
              <p
                className="text-sm text-[var(--terminal-text-muted)] mb-6"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                Please log in to access the chat interface and persist your conversations to the database.
              </p>
              <a
                href="/login"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[var(--amber-gold)] text-[var(--terminal-bg)] text-sm font-medium hover:shadow-[0_0_20px_var(--amber-gold)] transition-all"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                <Shield className="w-4 h-4" />
                AUTHENTICATE
              </a>
            </motion.div>
          </div>
        ) : isInitializing ? (
          /* Loading State */
          <div className="flex-1 flex flex-col items-center justify-center p-8">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-center"
            >
              <div className="relative w-16 h-16 mx-auto mb-6">
                <Loader2 className="w-16 h-16 text-[var(--phosphor-green)] animate-spin" />
              </div>
              <h2
                className="text-lg text-[var(--phosphor-green)] mb-2"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                ESTABLISHING DATABASE LINK...
              </h2>
              <p
                className="text-sm text-[var(--terminal-text-muted)]"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                Loading workspace and conversations
              </p>
            </motion.div>
          </div>
        ) : initError ? (
          /* Error State */
          <div className="flex-1 flex flex-col items-center justify-center p-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center max-w-md"
            >
              <div className="relative w-20 h-20 mx-auto mb-6">
                <div className="absolute inset-0 rounded-full bg-[var(--error-red)]/10" />
                <div className="absolute inset-2 rounded-full border-2 border-[var(--error-red)]/30 flex items-center justify-center">
                  <Activity className="w-8 h-8 text-[var(--error-red)]" />
                </div>
              </div>
              <h2
                className="text-xl text-[var(--error-red)] mb-3"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                CONNECTION ERROR
              </h2>
              <p
                className="text-sm text-[var(--terminal-text-muted)] mb-2"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                Failed to establish database connection:
              </p>
              <p
                className="text-xs text-[var(--error-red)] mb-6 p-3 rounded bg-[var(--error-red)]/10 border border-[var(--error-red)]/20"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                {initError}
              </p>
              <button
                onClick={() => window.location.reload()}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[var(--terminal-surface)] border border-[var(--terminal-border)] text-[var(--terminal-text)] text-sm font-medium hover:border-[var(--phosphor-green)]/30 transition-all"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                <Activity className="w-4 h-4" />
                RETRY CONNECTION
              </button>
            </motion.div>
          </div>
        ) : messages.length === 0 ? (
          <WelcomeState onPromptSelect={handlePromptSelect} selectedModel={selectedModel} />
        ) : (
          <div className="max-w-4xl mx-auto p-4">
            <AnimatePresence>
              {messages.map((message, index) => (
                <ChatMessage
                  key={index}
                  message={message}
                  index={index}
                  modelName={message.role === 'assistant' ? currentModel?.name : undefined}
                  isTyping={index === messages.length - 1 && isLoading && message.role === 'assistant'}
                  onCitationClick={(citations, clickedCitation) => {
                    setCitationPanelCitations(citations);
                    setActiveCitationId(clickedCitation.documentId);
                    setIsCitationPanelOpen(true);
                  }}
                />
              ))}
            </AnimatePresence>
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <ChatInput
        value={input}
        onChange={setInput}
        onSubmit={handleSubmit}
        onStop={handleStop}
        isLoading={isLoading}
        isModelLoading={isModelLoading}
        selectedModel={selectedModel}
        models={AVAILABLE_MODELS}
        onModelChange={handleModelChange}
      />

      {/* Citation Panel Sidebar */}
      <CitationPanel
        citations={citationPanelCitations}
        isOpen={isCitationPanelOpen}
        onClose={() => setIsCitationPanelOpen(false)}
        onCitationClick={(citation) => {
          setActiveCitationId(citation.documentId);
          // Navigate to document detail page
          router.push(`/documents/${citation.documentId}`);
        }}
        activeCitationId={activeCitationId}
      />
    </div>
  );
}

// Wrapper component with Suspense boundary for useSearchParams
export default function ChatPage() {
  return (
    <Suspense fallback={
      <div className="flex-1 flex flex-col items-center justify-center p-8">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-[var(--phosphor-green)] animate-spin mx-auto mb-4" />
          <p className="text-sm font-mono text-[var(--terminal-text-muted)]">
            Loading chat...
          </p>
        </div>
      </div>
    }>
      <ChatPageContent />
    </Suspense>
  );
}
