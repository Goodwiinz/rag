'use client';

import {
  ChatSettings,
  Conversation,
  Model,
} from '@/components/chat';
import { SimpleLayout } from '@/components/layout/SimpleLayout';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/authStore';
import { CreateMLCEngine, InitProgressReport, MLCEngine } from "@mlc-ai/web-llm";
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  ChevronDown,
  ChevronRight,
  Command,
  Cpu,
  Hexagon,
  LogOut,
  Menu,
  MessageSquare,
  Plus,
  Radio,
  Satellite,
  Send,
  Settings,
  Shield,
  Star,
  Terminal,
  User,
  X,
  Zap,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

// Available models with enhanced metadata
// Extended Model type with cloud support
interface ExtendedModel extends Model {
  isCloud?: boolean;
  provider?: 'openai' | 'local';
}

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

// Default settings
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

// Storage keys
const STORAGE_KEY = 'terminal-observatory-conversations';

// Message type matching Conversation interface
type MessageRole = 'user' | 'assistant';

// Citation from RAG retrieval
interface Citation {
  documentId: string;
  title: string;
  score: number;
}

interface Message {
  role: MessageRole;
  content: string;
  timestamp: number;
  citations?: Citation[];  // Retrieved documents used for this response
}

// Terminal Observatory Message Component
function TerminalMessage({
  message,
  isTyping,
  index,
  modelName,
}: {
  message: Message;
  isTyping?: boolean;
  isLast?: boolean;
  index: number;
  modelName?: string;
}) {
  const isUser = message.role === 'user';
  const timestamp = message.timestamp
    ? new Date(message.timestamp).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      })
    : '--:--:--';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, filter: 'blur(8px)' }}
      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      transition={{ duration: 0.4, delay: index * 0.05 }}
      className={cn(
        "group relative mb-6",
        isUser ? "ml-12" : "mr-12"
      )}
    >
      {/* Transmission Line */}
      <div
        className={cn(
          "absolute top-0 h-full w-[2px]",
          isUser
            ? "right-0 bg-gradient-to-b from-[#ffb700] to-transparent"
            : "left-0 bg-gradient-to-b from-[#00ff9f] to-transparent"
        )}
        style={{ opacity: 0.4 }}
      />

      {/* Message Header */}
      <div
        className={cn(
          "flex items-center gap-3 mb-2 text-xs",
          isUser ? "justify-end pr-4" : "pl-4"
        )}
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {!isUser && (
          <>
            <div className="flex items-center gap-2">
              <div className="signal-active" />
              <span className="text-[#00ff9f] uppercase tracking-wider">
                INCOMING TRANSMISSION
              </span>
            </div>
            {modelName && (
              <span className="text-[#3a3a4a]">
                [{modelName}]
              </span>
            )}
          </>
        )}
        {isUser && (
          <span className="text-[#ffb700] uppercase tracking-wider">
            OUTGOING QUERY
          </span>
        )}
        <span className="text-[#3a3a4a]">{timestamp}</span>
      </div>

      {/* Message Content */}
      <div
        className={cn(
          "relative rounded-lg overflow-hidden",
          isUser
            ? "bg-gradient-to-br from-[#1a1510] to-[#0d0d14] border border-[#3d2f1a] mr-4"
            : "bg-[#0d0d14] border border-[#1a1a28] ml-4"
        )}
      >
        {/* Holographic shimmer effect */}
        <div className="absolute inset-0 holo-shimmer opacity-50" />

        <div className="relative p-4">
          {isTyping ? (
            <div className="flex items-center gap-2 text-[#00ff9f] text-sm" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              <span className="transmission-cursor">Processing</span>
              <Activity className="w-4 h-4 animate-pulse" />
            </div>
          ) : (
            <div
              className={cn(
                "text-sm leading-relaxed",
                isUser ? "text-[#e8d5b5]" : "text-[#e0e0e8]"
              )}
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {isUser ? (
                <p className="whitespace-pre-wrap">{message.content}</p>
              ) : (
                <ReactMarkdown
                  components={{
                    code({ inline, className, children, ...props }: { inline?: boolean; className?: string; children?: React.ReactNode }) {
                      const match = /language-(\w+)/.exec(className || '');
                      const language = match ? match[1] : '';

                      return !inline && language ? (
                        <div className="my-3 rounded overflow-hidden border border-[#1a1a28]">
                          <div className="flex items-center justify-between bg-[#12121a] px-3 py-2 border-b border-[#1a1a28]">
                            <span className="text-[10px] text-[#00ff9f] uppercase tracking-wider" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                              {language}
                            </span>
                            <button
                              onClick={() => navigator.clipboard.writeText(String(children).replace(/\n$/, ''))}
                              className="text-[10px] text-[#6a6a7a] hover:text-[#00ff9f] transition-colors"
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
                              background: '#0a0a0f',
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
                          className="px-1.5 py-0.5 rounded bg-[#1a1a28] text-[#00ff9f] text-xs"
                          style={{ fontFamily: "'JetBrains Mono', monospace" }}
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    },
                    a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#00ff9f] hover:text-[#00cc7a] underline underline-offset-2"
                      >
                        {children}
                      </a>
                    ),
                    blockquote: ({ children }: { children?: React.ReactNode }) => (
                      <blockquote className="border-l-2 border-[#00ff9f] pl-4 my-2 italic text-[#6a6a7a]">
                        {children}
                      </blockquote>
                    ),
                    h1: ({ children }: { children?: React.ReactNode }) => (
                      <h1 className="text-xl font-bold text-[#00ff9f] mt-4 mb-2">{children}</h1>
                    ),
                    h2: ({ children }: { children?: React.ReactNode }) => (
                      <h2 className="text-lg font-bold text-[#00ff9f] mt-3 mb-2">{children}</h2>
                    ),
                    h3: ({ children }: { children?: React.ReactNode }) => (
                      <h3 className="text-base font-semibold text-[#00ff9f] mt-2 mb-1">{children}</h3>
                    ),
                    ul: ({ children }: { children?: React.ReactNode }) => (
                      <ul className="list-none space-y-1 my-2">
                        {children}
                      </ul>
                    ),
                    li: ({ children }: { children?: React.ReactNode }) => (
                      <li className="flex items-start gap-2">
                        <span className="text-[#00ff9f] mt-1">&#9657;</span>
                        <span>{children}</span>
                      </li>
                    ),
                    table: ({ children }: { children?: React.ReactNode }) => (
                      <div className="overflow-x-auto my-3">
                        <table className="w-full border-collapse border border-[#1a1a28]">
                          {children}
                        </table>
                      </div>
                    ),
                    th: ({ children }: { children?: React.ReactNode }) => (
                      <th className="border border-[#1a1a28] bg-[#12121a] px-3 py-2 text-left text-[10px] text-[#00ff9f] uppercase" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                        {children}
                      </th>
                    ),
                    td: ({ children }: { children?: React.ReactNode }) => (
                      <td className="border border-[#1a1a28] px-3 py-2 text-sm">
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

        {/* Citations Section - Show retrieved documents */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="border-t border-[#1a1a28] p-3 bg-[#0a0a0f]">
            <div 
              className="text-[10px] text-[#6a6a7a] uppercase tracking-wider mb-2"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              📚 RETRIEVED DOCUMENTS ({message.citations.length})
            </div>
            <div className="space-y-1">
              {message.citations.map((citation, idx) => (
                <div 
                  key={idx}
                  className="flex items-start gap-2 text-[11px] p-2 rounded bg-[#12121a] border border-[#1a1a28] hover:border-[#00ff9f]/30 transition-colors"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <span className="text-[#00ff9f] font-bold">[Doc {idx + 1}]</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-[#e0e0e8] truncate" title={citation.title}>
                      {citation.title.length > 60 ? citation.title.substring(0, 60) + '...' : citation.title}
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-[#6a6a7a]">
                      <span>ArXiv: {citation.documentId}</span>
                      <span>Score: {(citation.score * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Corner accent */}
        <div
          className={cn(
            "absolute bottom-0 w-8 h-8",
            isUser ? "left-0" : "right-0"
          )}
          style={{
            background: isUser
              ? 'linear-gradient(135deg, transparent 50%, rgba(255, 183, 0, 0.1) 50%)'
              : 'linear-gradient(-135deg, transparent 50%, rgba(0, 255, 159, 0.1) 50%)',
          }}
        />
      </div>
    </motion.div>
  );
}

// Terminal Model Selector
function TerminalModelSelector({
  models,
  selectedModelId,
  onModelChange,
  isLoading,
}: {
  models: Model[];
  selectedModelId?: string;
  onModelChange: (id: string) => void;
  isLoading?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const selectedModel = models.find(m => m.id === selectedModelId);

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isLoading}
        className={cn(
          "flex items-center gap-3 px-4 py-2 rounded border text-xs",
          "bg-[#0d0d14] border-[#1a1a28] text-[#e0e0e8]",
          "hover:border-[#00ff9f] hover:shadow-[0_0_12px_rgba(0,255,159,0.15)]",
          "transition-all duration-200",
          isLoading && "opacity-50 cursor-not-allowed"
        )}
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        <Cpu className="w-4 h-4 text-[#00ff9f]" />
        <span className="text-[#00ff9f]">
          {selectedModel ? selectedModel.name : 'SELECT NEURAL CORE'}
        </span>
        <ChevronRight className={cn(
          "w-4 h-4 text-[#3a3a4a] transition-transform",
          isOpen && "rotate-90"
        )} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
            className="absolute top-full left-0 mt-2 w-80 z-50"
          >
            <div className="terminal-window overflow-hidden">
              <div className="terminal-window-header">
                <div className="terminal-dot terminal-dot-red" />
                <div className="terminal-dot terminal-dot-yellow" />
                <div className="terminal-dot terminal-dot-green" />
                <span className="ml-2 text-xs text-[#6a6a7a]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  neural_cores.list
                </span>
              </div>
              <div className="p-2 max-h-80 overflow-y-auto terminal-scrollbar">
                {models.map((model, idx) => (
                  <motion.button
                    key={model.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.05 }}
                    onClick={() => {
                      onModelChange(model.id);
                      setIsOpen(false);
                    }}
                    className={cn(
                      "w-full text-left p-3 rounded transition-all",
                      "hover:bg-[#12121a] group",
                      selectedModelId === model.id && "bg-[#12121a] border-l-2 border-[#00ff9f]"
                    )}
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    <div className="flex items-center justify-between">
                      <span className={cn(
                        "text-xs font-semibold",
                        selectedModelId === model.id ? "text-[#00ff9f]" : "text-[#e0e0e8] group-hover:text-[#00ff9f]"
                      )}>
                        {model.name}
                      </span>
                      <div className="flex items-center gap-2">
                        {model.isFeatured && (
                          <Star className="w-3 h-3 text-[#ffb700] fill-[#ffb700]" />
                        )}
                        <span className={cn(
                          "text-[10px] px-1.5 py-0.5 rounded",
                          model.speed === 'Very Fast' && "bg-[#00ff9f]/10 text-[#00ff9f]",
                          model.speed === 'Fast' && "bg-[#00cc7a]/10 text-[#00cc7a]",
                          model.speed === 'Medium' && "bg-[#ffb700]/10 text-[#ffb700]"
                        )}>
                          {model.speed.toUpperCase()}
                        </span>
                      </div>
                    </div>
                    <p className="text-[10px] text-[#6a6a7a] mt-1">
                      {model.description}
                    </p>
                    <div className="flex items-center gap-3 mt-2 text-[10px] text-[#3a3a4a]">
                      <span>PARAMS: {model.parameters}</span>
                      <span>RAM: {model.ram}</span>
                      <span>ACC: {model.accuracy}%</span>
                    </div>
                  </motion.button>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Terminal Input Component
function TerminalInput({
  value,
  onChange,
  onSubmit,
  disabled,
  isLoading,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  isLoading?: boolean;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  }, [value]);

  return (
    <div className="relative">
      {/* Decorative grid lines */}
      <div className="absolute -top-4 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#1a1a28] to-transparent" />

      <div className={cn(
        "relative rounded-lg border overflow-hidden",
        "bg-[#0d0d14] border-[#1a1a28]",
        "focus-within:border-[#00ff9f] focus-within:shadow-[0_0_20px_rgba(0,255,159,0.1)]",
        "transition-all duration-200",
        disabled && "opacity-50"
      )}>
        {/* Input header */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-[#1a1a28] bg-[#0a0a0f]">
          <div className="flex items-center gap-2 text-[10px] text-[#3a3a4a]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            <Terminal className="w-3 h-3" />
            <span>QUERY_INPUT</span>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-[#3a3a4a]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            <span>{value.length} chars</span>
            <span className="text-[#6a6a7a]">SHIFT+ENTER for newline</span>
          </div>
        </div>

        <div className="flex items-end">
          <div className="flex-1 relative">
            {/* Command prompt */}
            <div className="absolute left-4 top-4 text-[#00ff9f] text-sm" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              <span className="phosphor-glow">&gt;</span>
            </div>
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              placeholder="Enter your query..."
              rows={1}
              className={cn(
                "w-full bg-transparent py-4 pl-10 pr-4",
                "text-sm text-[#e0e0e8] placeholder:text-[#3a3a4a]",
                "focus:outline-none resize-none",
                "min-h-[56px]"
              )}
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            />
          </div>

          <div className="p-3">
            <button
              onClick={onSubmit}
              disabled={disabled || !value.trim() || isLoading}
              className={cn(
                "flex items-center justify-center w-10 h-10 rounded",
                "text-xs transition-all duration-200",
                value.trim() && !disabled && !isLoading
                  ? "bg-[#00ff9f] text-[#0a0a0f] shadow-[0_0_20px_rgba(0,255,159,0.3)]"
                  : "bg-[#1a1a28] text-[#3a3a4a]"
              )}
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {isLoading ? (
                <Activity className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// User Avatar Dropdown Component
function UserAvatarDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuthStore();
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Get user initials for avatar
  const getInitials = (name?: string, email?: string) => {
    if (name) {
      const parts = name.split(' ');
      return parts.length > 1
        ? `${parts[0][0]}${parts[1][0]}`.toUpperCase()
        : parts[0].slice(0, 2).toUpperCase();
    }
    if (email) {
      return email.slice(0, 2).toUpperCase();
    }
    return 'AN';
  };

  const handleSignOut = () => {
    logout();
    router.push('/login');
  };

  const handleSettings = () => {
    setIsOpen(false);
    router.push('/settings');
  };

  if (!isAuthenticated) {
    return (
      <button
        onClick={() => router.push('/login')}
        className={cn(
          "flex items-center gap-2 px-3 py-1.5 rounded",
          "text-xs text-[#ffb700]",
          "bg-[#ffb700]/10 border border-[#ffb700]/20",
          "hover:bg-[#ffb700]/20 hover:border-[#ffb700]/40",
          "transition-all duration-200"
        )}
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        <User className="w-3 h-3" />
        SIGN IN
      </button>
    );
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex items-center gap-3 px-3 py-1.5 rounded border",
          "text-xs",
          "bg-[#0d0d14] border-[#1a1a28]",
          "hover:border-[#00ff9f]/30 hover:bg-[#12121a]",
          "transition-all duration-200",
          isOpen && "bg-[#12121a] border-[#00ff9f]/30"
        )}
      >
        {/* User Info */}
        <div className="flex flex-col items-end" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          <span className="text-[#e0e0e8] text-xs">
            {user?.name || 'User'}
          </span>
          <span className={cn(
            "text-[10px]",
            user?.role === 'admin' ? "text-[#ffb700]" : "text-[#00ff9f]"
          )}>
            {user?.role?.toUpperCase() || 'USER'}
          </span>
        </div>
        {/* Avatar */}
        <div className={cn(
          "w-8 h-8 rounded-full flex items-center justify-center",
          "bg-gradient-to-br from-[#00ff9f]/20 to-[#00cc7a]/20",
          "border border-[#00ff9f]/30",
          "text-[#00ff9f] text-xs font-semibold"
        )} style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          {getInitials(user?.name, user?.email)}
        </div>
        <ChevronDown className={cn(
          "w-3 h-3 text-[#3a3a4a] transition-transform",
          isOpen && "rotate-180"
        )} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute top-full right-0 mt-2 w-64 z-50"
          >
            <div className="terminal-window overflow-hidden">
              <div className="terminal-window-header">
                <div className="terminal-dot terminal-dot-red" />
                <div className="terminal-dot terminal-dot-yellow" />
                <div className="terminal-dot terminal-dot-green" />
                <span className="ml-2 text-xs text-[#6a6a7a]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  user_session.info
                </span>
              </div>

              {/* User Info */}
              <div className="p-4 border-b border-[#1a1a28]">
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "w-10 h-10 rounded-full flex items-center justify-center",
                    "bg-gradient-to-br from-[#00ff9f]/20 to-[#00cc7a]/20",
                    "border border-[#00ff9f]/30",
                    "text-[#00ff9f] text-sm font-semibold"
                  )} style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    {getInitials(user?.name, user?.email)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-[#e0e0e8] truncate" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {user?.name || 'Anonymous'}
                    </p>
                    <p className="text-[10px] text-[#6a6a7a] truncate" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {user?.email}
                    </p>
                  </div>
                </div>
                {user?.role && (
                  <div className="mt-2">
                    <span className={cn(
                      "text-[10px] px-2 py-0.5 rounded uppercase",
                      user.role === 'admin' && "bg-[#ffb700]/10 text-[#ffb700]",
                      user.role === 'user' && "bg-[#00ff9f]/10 text-[#00ff9f]",
                      user.role === 'viewer' && "bg-[#6a6a7a]/10 text-[#6a6a7a]"
                    )} style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {user.role}
                    </span>
                  </div>
                )}
              </div>

              {/* Menu Items */}
              <div className="p-2">
                <button
                  onClick={handleSettings}
                  className={cn(
                    "w-full flex items-center gap-3 px-3 py-2 rounded",
                    "text-xs text-[#e0e0e8]",
                    "hover:bg-[#12121a] hover:text-[#00ff9f]",
                    "transition-all duration-150"
                  )}
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <Settings className="w-4 h-4" />
                  <span>SETTINGS</span>
                </button>

                <div className="my-2 border-t border-[#1a1a28]" />

                <button
                  onClick={handleSignOut}
                  className={cn(
                    "w-full flex items-center gap-3 px-3 py-2 rounded",
                    "text-xs text-[#e0e0e8]",
                    "hover:bg-[#3d1a1a] hover:text-[#ff6b6b]",
                    "transition-all duration-150"
                  )}
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <LogOut className="w-4 h-4" />
                  <span>SIGN OUT</span>
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Main Page Component
export default function TerminalObservatoryChat() {
  // Core state
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState('');

  // Loading states
  const [isLoading, setIsLoading] = useState(false);
  const [isModelLoading, setIsModelLoading] = useState(false);
  const [progress, setProgress] = useState('');
  const [progressVal, setProgressVal] = useState(0);

  // UI state
  const [settings] = useState<ChatSettings>(DEFAULT_SETTINGS);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [currentTime, setCurrentTime] = useState<Date | null>(null);
  const [isMounted, setIsMounted] = useState(false);

  // Refs
  const engine = useRef<MLCEngine | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Update clock - only on client side to prevent hydration mismatch
  useEffect(() => {
    setIsMounted(true);
    setCurrentTime(new Date());
    const interval = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  // Load conversations from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        setConversations(JSON.parse(stored));
      } catch (e) {
        console.error('Failed to parse conversations:', e);
      }
    }
  }, []);

  // Save conversations
  useEffect(() => {
    if (conversations.length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    }
  }, [conversations]);

  // Load active conversation
  useEffect(() => {
    if (activeConversationId) {
      const conv = conversations.find(c => c.id === activeConversationId);
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
    const model = AVAILABLE_MODELS.find(m => m.id === modelId);
    
    // Skip WebLLM loading for cloud models
    if (model?.isCloud) {
      setProgress('Cloud model ready - no local loading required');
      setProgressVal(1);
      return;
    }
    
    setIsModelLoading(true);
    try {
      if (!engine.current) {
        engine.current = await CreateMLCEngine(modelId, { initProgressCallback });
      } else {
        await engine.current.reload(modelId);
      }
    } catch (err) {
      console.error('Failed to load model:', err);
    } finally {
      setIsModelLoading(false);
    }
  };

  // Send message
  const handleSubmit = async () => {
    if (!input.trim() || isLoading || isModelLoading || !selectedModel) return;

    const model = AVAILABLE_MODELS.find(m => m.id === selectedModel);
    const isCloudModel = model?.isCloud;

    // For local models, require engine to be initialized
    if (!isCloudModel && !engine.current) {
      console.error("Engine not initialized");
      return;
    }

    const userMessage = {
      role: 'user' as const,
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
      setConversations(prev => [newConv, ...prev]);
      setActiveConversationId(newConv.id);
    }

    try {
      let assistantMessage = '';

      if (isCloudModel) {
        // Use backend API for cloud models (GPT-4o mini via Azure OpenAI)
        // Send full conversation history for multi-turn support
        // Enable RAG to retrieve context from indexed documents
        const response = await fetch('/api/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            messages: newMessages.map(m => ({ role: m.role, content: m.content })),
            model: selectedModel,
            temperature: settings.temperature,
            max_tokens: settings.maxTokens,
            system_prompt: settings.systemPrompt,
            use_rag: true,  // Enable RAG to search indexed documents
            max_context_docs: 5,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || `API error: ${response.status}`);
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
          }
        ];

        setMessages(finalMessages);

        // Update conversation
        setConversations(prev =>
          prev.map(conv =>
            conv.id === currentConversationId
              ? { ...conv, messages: finalMessages, updatedAt: Date.now() }
              : conv
          )
        );
      } else {
        // Use local WebLLM engine for browser-based models
        const response = await engine.current!.chat.completions.create({
          messages: [
            { role: 'system', content: settings.systemPrompt },
            ...newMessages.map(m => ({ role: m.role, content: m.content }))
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
            }
          ]);
        }

        const finalMessages: Message[] = [
          ...newMessages,
          {
            role: 'assistant',
            content: assistantMessage,
            timestamp: Date.now(),
          }
        ];

        setMessages(finalMessages);

        // Update conversation
        setConversations(prev =>
          prev.map(conv =>
            conv.id === currentConversationId
              ? { ...conv, messages: finalMessages, updatedAt: Date.now() }
              : conv
          )
        );
      }
    } catch (err) {
      console.error('Failed to send message:', err);
      // Show error message to user
      setMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: `Error: ${err instanceof Error ? err.message : 'Failed to get response'}`,
          timestamp: Date.now(),
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Model change handler
  const handleModelChange = async (modelId: string) => {
    setSelectedModel(modelId);
    await loadModel(modelId);
  };

  // New conversation
  const createNewConversation = () => {
    setActiveConversationId(null);
    setMessages([]);
  };

  const currentModel = AVAILABLE_MODELS.find(m => m.id === selectedModel);

  return (
    <SimpleLayout showHeader={false}>
      <div className="h-screen flex flex-col star-field terminal-grid noise-texture">
        {/* Terminal Header */}
        <header className="relative z-10 border-b border-[#1a1a28] bg-[#0a0a0f]/90 backdrop-blur-xl">
          <div className="flex items-center justify-between px-6 py-3">
            {/* Left: Logo and Status */}
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-3">
                <div className="relative">
                  <Hexagon className="w-8 h-8 text-[#00ff9f]" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Terminal className="w-4 h-4 text-[#00ff9f]" />
                  </div>
                </div>
                <div>
                  <h1 className="text-sm font-bold text-[#e0e0e8] tracking-wider" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    TERMINAL OBSERVATORY
                  </h1>
                  <p className="text-[10px] text-[#3a3a4a]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    LOCAL NEURAL INTERFACE v2.0
                  </p>
                </div>
              </div>

              {/* Connection Status */}
              <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-[#0d0d14] border border-[#1a1a28]">
                <div className={cn(
                  "w-2 h-2 rounded-full",
                  selectedModel ? (currentModel?.isCloud ? "bg-[#ffb700] signal-active" : "bg-[#00ff9f] signal-active") : "bg-[#3a3a4a]"
                )} />
                <span className="text-[10px] text-[#6a6a7a]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  {selectedModel 
                    ? (currentModel?.isCloud ? 'CLOUD API CONNECTED' : 'NEURAL LINK ACTIVE') 
                    : 'AWAITING CONNECTION'}
                </span>
              </div>
            </div>

            {/* Center: Model Selector */}
            <div className="flex items-center gap-4">
              <TerminalModelSelector
                models={AVAILABLE_MODELS}
                selectedModelId={selectedModel}
                onModelChange={handleModelChange}
                isLoading={isModelLoading}
              />
            </div>

            {/* Right: Time and Controls */}
            <div className="flex items-center gap-4">
              <div className="text-xs text-[#3a3a4a]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                <span className="text-[#6a6a7a]">UTC </span>
                <span className="text-[#00ff9f]" suppressHydrationWarning>
                  {currentTime ? currentTime.toISOString().split('T')[1].split('.')[0] : '--:--:--'}
                </span>
              </div>

              <button
                onClick={createNewConversation}
                className={cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded",
                  "text-xs text-[#00ff9f]",
                  "bg-[#00ff9f]/10 border border-[#00ff9f]/20",
                  "hover:bg-[#00ff9f]/20 hover:border-[#00ff9f]/40",
                  "transition-all duration-200"
                )}
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                <Plus className="w-3 h-3" />
                NEW SESSION
              </button>

              {/* User Avatar Dropdown */}
              <UserAvatarDropdown />

              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className={cn(
                  "p-2 rounded",
                  "text-[#6a6a7a] hover:text-[#00ff9f]",
                  "hover:bg-[#1a1a28]",
                  "transition-all duration-200"
                )}
              >
                <Menu className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Model Loading Progress */}
          <AnimatePresence>
            {isModelLoading && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="border-t border-[#1a1a28] overflow-hidden"
              >
                <div className="px-6 py-3 bg-[#0a0a0f]">
                  <div className="flex items-center gap-4">
                    <div className="relative">
                      <Radio className="w-5 h-5 text-[#00ff9f] animate-pulse" />
                      <div className="absolute inset-0 flex items-center justify-center">
                        <div className="w-2 h-2 rounded-full bg-[#00ff9f] animate-ping" />
                      </div>
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-[#00ff9f]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                          ESTABLISHING NEURAL LINK...
                        </span>
                        <span className="text-xs text-[#6a6a7a]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                          {Math.round(progressVal * 100)}%
                        </span>
                      </div>
                      <div className="h-1 bg-[#1a1a28] rounded-full overflow-hidden">
                        <motion.div
                          className="h-full bg-gradient-to-r from-[#00ff9f] to-[#00cc7a]"
                          initial={{ width: 0 }}
                          animate={{ width: `${progressVal * 100}%` }}
                          transition={{ duration: 0.3 }}
                        />
                      </div>
                      <p className="text-[10px] text-[#3a3a4a] mt-1 truncate" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                        {progress}
                      </p>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </header>

        {/* Main Content */}
        <main className="flex-1 flex overflow-hidden">
          {/* Chat Area */}
          <div className="flex-1 flex flex-col">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto terminal-scrollbar px-6 py-8">
              <div className="max-w-4xl mx-auto">
                {/* Empty State */}
                {messages.length === 0 && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex flex-col items-center justify-center py-20"
                  >
                    {/* Orbital decoration */}
                    <div className="relative mb-8">
                      <div className="absolute inset-0 flex items-center justify-center">
                        <div className="w-32 h-32 rounded-full border border-[#1a1a28] animate-spin" style={{ animationDuration: '20s' }} />
                      </div>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <div className="w-48 h-48 rounded-full border border-[#1a1a28]/50 animate-spin" style={{ animationDuration: '30s', animationDirection: 'reverse' }} />
                      </div>
                      <div className="relative w-24 h-24 flex items-center justify-center">
                        <Satellite className="w-12 h-12 text-[#00ff9f] float-gentle" />
                      </div>
                    </div>

                    <h2 className="text-xl text-[#e0e0e8] tracking-wider mb-2" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {selectedModel ? 'NEURAL LINK ESTABLISHED' : 'AWAITING NEURAL CORE SELECTION'}
                    </h2>
                    <p className="text-sm text-[#3a3a4a] text-center max-w-md" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {selectedModel
                        ? 'Ready to receive transmissions. Enter your query below.'
                        : 'Select a neural core from the command bar to initialize the interface.'}
                    </p>

                    {selectedModel && (
                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 }}
                        className="mt-8 grid grid-cols-2 gap-4 max-w-lg"
                      >
                        {[
                          { icon: Zap, label: 'RAPID PROCESSING', desc: 'Sub-second response latency' },
                          { icon: Shield, label: 'LOCAL ONLY', desc: 'All data stays on device' },
                          { icon: Cpu, label: 'NEURAL INFERENCE', desc: 'Advanced language model' },
                          { icon: Activity, label: 'REAL-TIME STREAM', desc: 'Live response generation' },
                        ].map((item, idx) => (
                          <div
                            key={idx}
                            className="p-4 rounded-lg border border-[#1a1a28] bg-[#0d0d14]/50"
                          >
                            <item.icon className="w-5 h-5 text-[#00ff9f] mb-2" />
                            <h3 className="text-xs text-[#e0e0e8] mb-1" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{item.label}</h3>
                            <p className="text-[10px] text-[#3a3a4a]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{item.desc}</p>
                          </div>
                        ))}
                      </motion.div>
                    )}
                  </motion.div>
                )}

                {/* Messages */}
                <AnimatePresence>
                  {messages.map((message, idx) => (
                    <TerminalMessage
                      key={idx}
                      message={message}
                      index={idx}
                      isTyping={idx === messages.length - 1 && isLoading && message.role === 'assistant'}
                      isLast={idx === messages.length - 1}
                      modelName={message.role === 'assistant' ? currentModel?.name : undefined}
                    />
                  ))}
                </AnimatePresence>

                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Input Area */}
            <div className="border-t border-[#1a1a28] bg-[#0a0a0f]/90 backdrop-blur-xl p-6">
              <div className="max-w-4xl mx-auto">
                <TerminalInput
                  value={input}
                  onChange={setInput}
                  onSubmit={handleSubmit}
                  disabled={!selectedModel || isModelLoading}
                  isLoading={isLoading}
                />

                {/* Footer info */}
                <div className="flex items-center justify-between mt-3 px-1">
                  <div className="flex items-center gap-4 text-[10px] text-[#3a3a4a]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    <span className="flex items-center gap-1">
                      <Command className="w-3 h-3" />
                      ENTER to send
                    </span>
                    <span>|</span>
                    <span>All processing runs locally in your browser</span>
                  </div>
                  {currentModel && (
                    <span className="text-[10px] text-[#3a3a4a]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      Active: <span className="text-[#00ff9f]">{currentModel.name}</span>
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <AnimatePresence>
            {sidebarOpen && (
              <motion.aside
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: 320, opacity: 1 }}
                exit={{ width: 0, opacity: 0 }}
                className="border-l border-[#1a1a28] bg-[#0a0a0f] overflow-hidden"
              >
                <div className="h-full flex flex-col">
                  {/* Sidebar Header */}
                  <div className="flex items-center justify-between px-4 py-3 border-b border-[#1a1a28]">
                    <span className="text-xs text-[#6a6a7a]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>SESSION LOGS</span>
                    <button
                      onClick={() => setSidebarOpen(false)}
                      className="text-[#3a3a4a] hover:text-[#00ff9f] transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Conversations List */}
                  <div className="flex-1 overflow-y-auto terminal-scrollbar p-2">
                    {conversations.length === 0 ? (
                      <div className="text-center py-8">
                        <MessageSquare className="w-8 h-8 text-[#1a1a28] mx-auto mb-2" />
                        <p className="text-xs text-[#3a3a4a]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>No sessions logged</p>
                      </div>
                    ) : (
                      conversations.map((conv) => (
                        <button
                          key={conv.id}
                          onClick={() => {
                            setActiveConversationId(conv.id);
                            setSidebarOpen(false);
                          }}
                          className={cn(
                            "w-full text-left p-3 rounded mb-1 transition-all",
                            "hover:bg-[#12121a] group",
                            activeConversationId === conv.id && "bg-[#12121a] border-l-2 border-[#00ff9f]"
                          )}
                          style={{ fontFamily: "'JetBrains Mono', monospace" }}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <p className={cn(
                                "text-xs truncate",
                                activeConversationId === conv.id ? "text-[#00ff9f]" : "text-[#e0e0e8]"
                              )}>
                                {conv.title}
                              </p>
                              <p className="text-[10px] text-[#3a3a4a] mt-1">
                                {new Date(conv.updatedAt).toLocaleDateString()} - {conv.messages.length} messages
                              </p>
                            </div>
                          </div>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              </motion.aside>
            )}
          </AnimatePresence>
        </main>
      </div>
    </SimpleLayout>
  );
}
