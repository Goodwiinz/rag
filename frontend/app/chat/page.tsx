'use client';

import {
  ChatSettings,
  Conversation,
  Model,
} from '@/components/chat';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/authStore';
import { CreateMLCEngine, InitProgressReport, MLCEngine } from "@mlc-ai/web-llm";
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  ArrowUp,
  BookOpen,
  ChevronDown,
  Cpu,
  FileText,
  Mic,
  Paperclip,
  Radio,
  Shield,
  Sparkles,
  Square,
  Zap,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

// ============================================
// TYPES
// ============================================

interface ExtendedModel extends Model {
  isCloud?: boolean;
  provider?: 'openai' | 'local';
}

interface Citation {
  documentId: string;
  title: string;
  score: number;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Citation[];
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

const STORAGE_KEY = 'terminal-observatory-conversations';
const ACTIVE_CONV_KEY = 'terminal-observatory-active-conversation';

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
}: {
  message: Message;
  index: number;
  modelName?: string;
  isTyping?: boolean;
}) {
  const isUser = message.role === 'user';
  const timestamp = message.timestamp
    ? new Date(message.timestamp).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })
    : '--:--';

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.02 }}
      className={cn('group relative mb-6', isUser ? 'ml-16' : 'mr-16')}
    >
      {/* Transmission Line */}
      <div
        className={cn(
          'absolute top-0 h-full w-[2px]',
          isUser
            ? 'right-0 bg-gradient-to-b from-[var(--amber-gold)] to-transparent'
            : 'left-0 bg-gradient-to-b from-[var(--phosphor-green)] to-transparent'
        )}
        style={{ opacity: 0.4 }}
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
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--phosphor-green)] signal-active" />
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
              className="flex items-center gap-2 text-[var(--phosphor-green)] text-sm"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              <span className="transmission-cursor">Processing</span>
              <Activity className="w-4 h-4 animate-pulse" />
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
                <ReactMarkdown
                  components={{
                    code({
                      inline,
                      className,
                      children,
                      ...props
                    }: {
                      inline?: boolean;
                      className?: string;
                      children?: React.ReactNode;
                    }) {
                      const match = /language-(\w+)/.exec(className || '');
                      const language = match ? match[1] : '';

                      return !inline && language ? (
                        <div className="my-3 rounded overflow-hidden border border-[var(--terminal-border)]">
                          <div className="flex items-center justify-between bg-[var(--terminal-bg)] px-3 py-2 border-b border-[var(--terminal-border)]">
                            <span
                              className="text-[10px] text-[var(--phosphor-green)] uppercase tracking-wider"
                              style={{ fontFamily: "'JetBrains Mono', monospace" }}
                            >
                              {language}
                            </span>
                            <button
                              onClick={() =>
                                navigator.clipboard.writeText(
                                  String(children).replace(/\n$/, '')
                                )
                              }
                              className="text-[10px] text-[var(--terminal-text-muted)] hover:text-[var(--phosphor-green)] transition-colors"
                              style={{ fontFamily: "'JetBrains Mono', monospace" }}
                            >
                              [COPY]
                            </button>
                          </div>
                          <SyntaxHighlighter
                            style={atomDark}
                            language={language}
                            PreTag="div"
                            customStyle={{
                              margin: 0,
                              background: 'var(--terminal-bg)',
                              fontSize: '12px',
                              fontFamily: "'JetBrains Mono', monospace",
                            }}
                            {...props}
                          >
                            {String(children).replace(/\n$/, '')}
                          </SyntaxHighlighter>
                        </div>
                      ) : (
                        <code
                          className="px-1.5 py-0.5 rounded bg-[var(--terminal-border)] text-[var(--phosphor-green)] text-xs"
                          style={{ fontFamily: "'JetBrains Mono', monospace" }}
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    },
                    a: ({
                      href,
                      children,
                    }: {
                      href?: string;
                      children?: React.ReactNode;
                    }) => (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[var(--phosphor-green)] hover:text-[var(--phosphor-green-dim)] underline underline-offset-2"
                      >
                        {children}
                      </a>
                    ),
                    blockquote: ({ children }: { children?: React.ReactNode }) => (
                      <blockquote className="border-l-2 border-[var(--phosphor-green)] pl-4 my-2 italic text-[var(--terminal-text-muted)]">
                        {children}
                      </blockquote>
                    ),
                    h1: ({ children }: { children?: React.ReactNode }) => (
                      <h1 className="text-xl font-bold text-[var(--phosphor-green)] mt-4 mb-2">
                        {children}
                      </h1>
                    ),
                    h2: ({ children }: { children?: React.ReactNode }) => (
                      <h2 className="text-lg font-bold text-[var(--phosphor-green)] mt-3 mb-2">
                        {children}
                      </h2>
                    ),
                    h3: ({ children }: { children?: React.ReactNode }) => (
                      <h3 className="text-base font-semibold text-[var(--phosphor-green)] mt-2 mb-1">
                        {children}
                      </h3>
                    ),
                    ul: ({ children }: { children?: React.ReactNode }) => (
                      <ul className="list-none space-y-1 my-2">{children}</ul>
                    ),
                    li: ({ children }: { children?: React.ReactNode }) => (
                      <li className="flex items-start gap-2">
                        <span className="text-[var(--phosphor-green)] mt-1">▷</span>
                        <span>{children}</span>
                      </li>
                    ),
                  }}
                >
                  {message.content}
                </ReactMarkdown>
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

  return (
    <div className="border-t border-[var(--terminal-border)] bg-[var(--terminal-bg)]/95 backdrop-blur-xl">
      <div className="max-w-4xl mx-auto p-4">
        <div className="terminal-window p-3">
          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
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
                className="text-[10px] text-[var(--terminal-text-muted)]"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                {value.length} chars
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
        </div>

        {/* Keyboard Hint */}
        <div
          className="flex items-center justify-center gap-4 mt-2 text-[10px] text-[var(--terminal-text-muted)]"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          <span>
            <kbd className="px-1 py-0.5 rounded bg-[var(--terminal-surface)] border border-[var(--terminal-border)]">
              Enter
            </kbd>{' '}
            to send
          </span>
          <span>
            <kbd className="px-1 py-0.5 rounded bg-[var(--terminal-surface)] border border-[var(--terminal-border)]">
              Shift+Enter
            </kbd>{' '}
            for new line
          </span>
        </div>
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

export default function ChatPage() {
  // Core state
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState<string>('');

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
  const isHydratedRef = useRef(false);

  // Auth
  const { isAuthenticated } = useAuthStore();

  // Load conversations and active conversation from localStorage (runs first on mount)
  useEffect(() => {
    try {
      // Load conversations
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setConversations(parsed);
          console.log('[Chat] Loaded', parsed.length, 'conversations from storage');

          // Load and restore active conversation
          const activeId = localStorage.getItem(ACTIVE_CONV_KEY);
          if (activeId && parsed.some((c: Conversation) => c.id === activeId)) {
            setActiveConversationId(activeId);
            const activeConv = parsed.find((c: Conversation) => c.id === activeId);
            if (activeConv) {
              setMessages(activeConv.messages);
              console.log('[Chat] Restored active conversation:', activeConv.title);
            }
          }
        }
      }
    } catch (e) {
      console.error('[Chat] Failed to parse conversations:', e);
    }
    // Delay setting hydrated flag until after React flushes state updates
    // This prevents the save effect from running with stale state
    setTimeout(() => {
      isHydratedRef.current = true;
      console.log('[Chat] Hydration complete');
    }, 0);
  }, []);

  // Save conversations to localStorage (only after hydration)
  useEffect(() => {
    // Skip saving during initial hydration to prevent overwriting stored data
    if (!isHydratedRef.current) {
      return;
    }
    // Save conversations (including empty array to clear storage when all deleted)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    console.log('[Chat] Saved', conversations.length, 'conversations to storage');
  }, [conversations]);

  // Save active conversation ID
  useEffect(() => {
    if (!isHydratedRef.current) {
      return;
    }
    if (activeConversationId) {
      localStorage.setItem(ACTIVE_CONV_KEY, activeConversationId);
    } else {
      localStorage.removeItem(ACTIVE_CONV_KEY);
    }
  }, [activeConversationId]);

  // Load active conversation
  useEffect(() => {
    if (activeConversationId) {
      const conv = conversations.find((c) => c.id === activeConversationId);
      if (conv) {
        setMessages(conv.messages);
      }
    }
  }, [activeConversationId, conversations]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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

    // Create new conversation if needed
    let currentConversationId = activeConversationId;
    if (!currentConversationId) {
      const newConv: Conversation = {
        id: crypto.randomUUID(),
        title: input.trim().substring(0, 50),
        messages: newMessages,
        modelId: selectedModel,
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      currentConversationId = newConv.id;
      setConversations((prev) => [newConv, ...prev]);
      setActiveConversationId(newConv.id);
    }

    try {
      let assistantMessage = '';

      if (isCloudModel) {
        // Use backend API for cloud models (GPT-4o mini via Azure OpenAI)
        const response = await fetch('/api/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            messages: newMessages.map((m) => ({ role: m.role, content: m.content })),
            model: selectedModel,
            temperature: settings.temperature,
            max_tokens: settings.maxTokens,
            system_prompt: settings.systemPrompt,
            use_rag: true,
            max_context_docs: 5,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || 'API error: ' + response.status);
        }

        const data = await response.json();
        assistantMessage = data.message?.content || 'No response from the model.';

        // Extract citations from retrieved contexts
        const citations: Citation[] = (data.retrieved_contexts || []).map((ctx: any) => ({
          documentId: ctx.document_id,
          title: ctx.title,
          score: ctx.score,
        }));

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
      setMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: 'Error: ' + (err instanceof Error ? err.message : 'Failed to get response'),
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
      <div className="flex-1 overflow-y-auto terminal-scrollbar">
        {messages.length === 0 ? (
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
    </div>
  );
}
