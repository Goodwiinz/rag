'use client';

import {
  ChatSettings,
  CitationPanel,
  Model,
  RAGToggle,
} from '@/components/chat';
import { ChatHeader } from '@/components/chat/ChatHeader';
import { ChatSidebar } from '@/components/chat/ChatSidebar';
import {
  selectDisplayedMessages,
  syncConversationMessagesWithStore,
} from '@/components/chat/shared/cloudMessageView';
import {
  getNewChatUrl,
  getSelectedThreadUrl,
} from '@/components/chat/shared/chatNavigation';
import { TerminalChatBubble } from '@/components/chat/shared/TerminalChatBubble';
import { upsertConversationFromThreadDetail } from '@/components/chat/shared/threadConversationState';
import { buildThreadCreateRequest } from '@/components/chat/shared/threadCreation';
import { cn } from '@/lib/utils';
import {
  buildRAGSystemPrompt,
  getModelAwareHistory,
  getModelSize,
  getRAGConfigForModel,
  RAGContextItem,
  ragService,
} from '@/services/ragService';
import { workspaceService } from '@/services/workspaceService';
import { useChatStore } from '@/store/chat-store';
import { useAuthStore } from '@/stores/authStore';
import {
  CitationCreate,
  ChatMessage as DBChatMessage,
  Conversation as DBConversation,
  MessageRole,
  Thread,
  Workspace,
} from '@/types/workspace';
import {
  Citation,
  getReferencedItemsByCitationIndex,
} from '@/utils/citationParser';
import type { InitProgressReport, MLCEngine } from '@mlc-ai/web-llm';
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useSpring,
  useTransform,
} from 'framer-motion';
import {
  Activity,
  ArrowDown,
  ArrowUp,
  BookOpen,
  ChevronDown,
  Cpu,
  FileText,
  Loader2,
  Mic,
  Paperclip,
  Radio,
  Satellite,
  Shield,
  Sparkles,
  Square,
  Zap,
} from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useEffect, useRef, useState } from 'react';

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

import { normalizeCitation } from '@/utils/citationNormalizer';

interface ExtendedModel extends Model {
  isCloud?: boolean;
  provider?: 'openai' | 'local';
}

interface Message {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  citations?: Citation[];
  diagnosticsTraceId?: string;
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
  previewText?: string;
  messageCount?: number;
}

// ============================================
// CONSTANTS
// ============================================

// Wait for Zustand store loadMessages to propagate after streaming completes
const STORE_PROPAGATION_DELAY_MS = 200;

const AVAILABLE_MODELS: ExtendedModel[] = [
  {
    id: 'gpt-4o',
    name: 'GPT-4O',
    description:
      'OpenAI flagship model with superior reasoning and multimodal capabilities',
    size: 'Cloud',
    parameters: 'Cloud API',
    ram: 'N/A',
    speed: 'Fast',
    accuracy: 97,
    features: [
      'Advanced Reasoning',
      'Code Generation',
      'Multimodal',
      'Function Calling',
    ],
    tags: ['openai', 'cloud', 'flagship'],
    isRecommended: true,
    isFeatured: true,
    isCloud: true,
    provider: 'openai',
    benchmarks: { reasoning: 96, coding: 95, math: 94, language: 97 },
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
    benchmarks: { reasoning: 72, coding: 65, math: 70, language: 82 },
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
    benchmarks: { reasoning: 81, coding: 78, math: 79, language: 88 },
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
    benchmarks: { reasoning: 79, coding: 80, math: 76, language: 91 },
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
    benchmarks: { reasoning: 85, coding: 83, math: 82, language: 87 },
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
    benchmarks: { reasoning: 76, coding: 71, math: 74, language: 86 },
  },
];

const DEFAULT_SETTINGS: ChatSettings = {
  temperature: 0.7,
  maxTokens: 2048,
  topP: 0.9,
  frequencyPenalty: 0,
  presencePenalty: 0,
  systemPrompt:
    'You are an advanced AI assistant operating within the Terminal Observatory. Provide precise, well-structured responses.',
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

const _STARTER_PROMPTS = [
  {
    icon: BookOpen,
    title: 'Summarize Research',
    prompt:
      'Summarize the key findings from the recent papers on RAG optimization',
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
          'flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all duration-200',
          'bg-[var(--terminal-surface)] border-[var(--terminal-border)]',
          'hover:border-[var(--phosphor-green)]/30',
          'active:scale-[0.98]',
          isOpen &&
            'border-[var(--phosphor-green)]/50 bg-[var(--phosphor-green)]/5',
          isLoading && 'opacity-50 cursor-not-allowed'
        )}
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        <Cpu
          className={cn(
            'w-3.5 h-3.5 transition-colors',
            isOpen
              ? 'text-[var(--phosphor-green)] animate-pulse'
              : 'text-[var(--phosphor-green)]'
          )}
        />
        <span className="text-[var(--terminal-text)] text-xs">
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
  enableRAG,
  onRAGToggle,
  isRAGLoading,
  inputRef,
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
  enableRAG: boolean;
  onRAGToggle: (enabled: boolean) => void;
  isRAGLoading?: boolean;
  inputRef?: React.RefObject<HTMLTextAreaElement>;
}) {
  const internalRef = useRef<HTMLTextAreaElement>(null);
  const textareaRef = inputRef ?? internalRef;
  const [isFocused, setIsFocused] = useState(false);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 200) + 'px';
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
    <div className="z-40 bg-[var(--terminal-bg)] pt-2 pb-4 px-4 border-t border-[var(--terminal-border)]">
      <div className="max-w-4xl mx-auto">
        <motion.div
          className={cn(
            'relative rounded-lg overflow-visible transition-all duration-300',
            'bg-[#0A0A0A] border border-[var(--terminal-border)]',
            isFocused &&
              'border-[var(--phosphor-green)]/30 ring-1 ring-[var(--phosphor-green)]/10 shadow-[0_0_15px_-5px_rgba(0,255,159,0.1)]'
          )}
        >
          {/* Top Bar: Model Selector, RAG Toggle & Status */}
          <div className="flex items-center justify-between px-4 py-1.5 bg-[var(--terminal-elevated)]/50 border-b border-[var(--terminal-border)] rounded-t-xl">
            <div className="flex items-center gap-3">
              <ModelSelector
                models={models}
                selectedModelId={selectedModel}
                onModelChange={onModelChange}
                isLoading={isModelLoading}
              />
              {/* RAG Toggle - Show for all models */}
              {selectedModel && (
                <RAGToggle
                  enabled={enableRAG}
                  onToggle={onRAGToggle}
                  isLoading={isRAGLoading}
                  disabled={isLoading}
                />
              )}
            </div>
            <div className="flex items-center gap-3">
              {/* RAG loading indicator */}
              {isRAGLoading && (
                <span
                  className="text-[9px] text-[var(--phosphor-green)] animate-pulse"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  RETRIEVING...
                </span>
              )}
              <span
                className={cn(
                  'text-[9px] transition-colors',
                  isNearLimit
                    ? 'text-[var(--amber-gold)]'
                    : 'text-[var(--terminal-text-dim)]'
                )}
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                {charCount}/{maxChars}
              </span>
            </div>
          </div>

          <div className="p-3 sm:p-4">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              placeholder="Inject query into neural stream..."
              rows={1}
              className="w-full bg-transparent text-[var(--terminal-text)] text-sm resize-none outline-none placeholder:text-[var(--terminal-text-dim)]/50 selection:bg-[var(--phosphor-green)]/20 selection:text-[var(--phosphor-green)]"
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                minHeight: '44px',
                maxHeight: '200px',
              }}
              disabled={isDisabled}
            />

            <div className="flex items-center justify-between mt-2">
              <div className="flex items-center gap-1">
                <button
                  className="p-2 rounded-lg hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] transition-colors group"
                  title="Attach artifact"
                >
                  <Paperclip className="w-4 h-4 group-hover:text-[var(--phosphor-green)] transition-colors" />
                </button>
                <button
                  className="p-2 rounded-lg hover:bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] transition-colors group"
                  title="Voice input"
                >
                  <Mic className="w-4 h-4 group-hover:text-[var(--phosphor-green)] transition-colors" />
                </button>
              </div>

              {isLoading ? (
                <button
                  onClick={onStop}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--error-red)]/10 border border-[var(--error-red)]/50 text-[var(--error-red)] text-[10px] font-bold hover:bg-[var(--error-red)]/20 transition-all shadow-[0_0_10px_rgba(239,68,68,0.05)]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <Square className="w-3 h-3" />
                  HALT
                </button>
              ) : (
                <button
                  onClick={onSubmit}
                  disabled={!value.trim() || isDisabled}
                  className={cn(
                    'flex items-center gap-2 px-6 py-2 rounded text-[10px] font-bold tracking-widest transition-all duration-300',
                    value.trim() && !isDisabled
                      ? 'bg-[var(--phosphor-green)] text-[#0A0A0A] hover:bg-[var(--phosphor-green)]/90 hover:shadow-[0_0_15px_rgba(0,255,159,0.3)] active:scale-95'
                      : 'bg-transparent text-[var(--terminal-text-dim)] border border-[var(--terminal-border)] cursor-not-allowed'
                  )}
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  TRANSMIT
                  <ArrowUp className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        </motion.div>

        {/* Keyboard Hint */}
        <motion.div
          initial={{ opacity: 0.5 }}
          animate={{ opacity: isFocused ? 0.3 : 0.5 }}
          className="flex items-center justify-center gap-4 mt-2 text-[9px] text-[var(--terminal-text-dim)] uppercase tracking-tighter"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          <span>[Enter] Send</span>
          <span>[Shift+Enter] Line Break</span>
          <span className="hidden sm:inline">[/] Commands</span>
        </motion.div>
      </div>
    </div>
  );
}

// ============================================
// WELCOME STATE
// ============================================

function WelcomeState({
  onPromptSelect: _onPromptSelect,
  selectedModel,
}: {
  onPromptSelect: (prompt: string) => void;
  selectedModel?: string;
}) {
  // Mouse tracking for parallax effect
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    x.set(e.clientX - centerX);
    y.set(e.clientY - centerY);
  };

  const handleMouseLeave = () => {
    x.set(0);
    y.set(0);
  };

  // Smooth spring physics for the tilt
  const springConfig = { damping: 25, stiffness: 150 };
  const rotateX = useSpring(
    useTransform(y, [-100, 100], [10, -10]),
    springConfig
  );
  const rotateY = useSpring(
    useTransform(x, [-100, 100], [-10, 10]),
    springConfig
  );

  return (
    <div
      className="flex-1 flex flex-col items-center justify-center p-8 perspective-1000"
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.8 }}
        style={{ rotateX, rotateY, transformStyle: 'preserve-3d' }}
        className="text-center max-w-2xl relative"
      >
        {/* Orbital decoration */}
        <div className="relative mb-12 flex items-center justify-center h-64 w-64 mx-auto transform-gpu">
          {/* Outer Ring - Counter Rotate */}
          <motion.div
            style={{ translateZ: 20 }}
            className="absolute inset-0 flex items-center justify-center"
          >
            <div className="w-56 h-56 rounded-full border border-[#1a1a28]/50 animate-[spin_30s_linear_infinite_reverse] orbital-ring-reverse" />
          </motion.div>

          {/* Inner Ring - Rotate */}
          <motion.div
            style={{ translateZ: 40 }}
            className="absolute inset-0 flex items-center justify-center"
          >
            <div className="w-32 h-32 rounded-full border border-[#1a1a28] animate-[spin_20s_linear_infinite] orbital-ring" />
          </motion.div>

          {/* Core Container */}
          <motion.div
            style={{ translateZ: 60 }}
            className="relative w-24 h-24 flex items-center justify-center"
          >
            {/* Satellite Icon with Float */}
            <Satellite className="w-12 h-12 text-[#00ff9f] float-gentle drop-shadow-[0_0_15px_rgba(0,255,159,0.3)]" />

            {/* Scanning Beam Effect */}
            <motion.div
              animate={{ top: ['0%', '100%', '0%'], opacity: [0, 1, 0] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
              className="absolute left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-[#00ff9f] to-transparent w-full"
            />
          </motion.div>

          {/* Radar Pings - Background */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div
              className="w-full h-full rounded-full border border-[#00ff9f]/5 animate-ping"
              style={{ animationDuration: '3s' }}
            />
          </div>
        </div>

        <motion.div style={{ translateZ: 30 }}>
          <h2
            className="text-xl text-[#e0e0e8] tracking-wider mb-2"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {selectedModel
              ? 'NEURAL LINK ESTABLISHED'
              : 'AWAITING NEURAL CORE SELECTION'}
          </h2>
          <p
            className="text-sm text-[#3a3a4a] text-center max-w-md mx-auto"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {selectedModel
              ? 'Ready to receive transmissions. Enter your query below.'
              : 'Select a neural core from the command bar to initialize the interface.'}
          </p>
        </motion.div>

        {selectedModel && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            style={{ translateZ: 20 }}
            className="mt-8 grid grid-cols-2 gap-4 max-w-lg mx-auto"
          >
            {[
              {
                icon: Zap,
                label: 'RAPID PROCESSING',
                desc: 'Sub-second response latency',
              },
              {
                icon: Shield,
                label: 'LOCAL ONLY',
                desc: 'All data stays on device',
              },
              {
                icon: Cpu,
                label: 'NEURAL INFERENCE',
                desc: 'Advanced language model',
              },
              {
                icon: Activity,
                label: 'REAL-TIME STREAM',
                desc: 'Live response generation',
              },
            ].map((item, idx) => (
              <div
                key={idx}
                className="p-4 rounded-lg border border-[#1a1a28] bg-[#0d0d14]/50 text-left hover:border-[#00ff9f]/20 transition-all group backdrop-blur-sm"
              >
                <item.icon className="w-5 h-5 text-[#00ff9f] mb-2 group-hover:scale-110 transition-transform" />
                <h3
                  className="text-xs text-[#e0e0e8] mb-1"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  {item.label}
                </h3>
                <p
                  className="text-[10px] text-[#3a3a4a]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  {item.desc}
                </p>
              </div>
            ))}
          </motion.div>
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
                INITIALIZING...
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
  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState<string>('gpt-4o');

  // Database state
  const [_workspace, setWorkspace] = useState<Workspace | null>(null);
  const [dbConversation, setDbConversation] = useState<DBConversation | null>(
    null
  );
  const [_activeThread, setActiveThread] = useState<Thread | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [initError, setInitError] = useState<string | null>(null);

  // Loading states
  const [isLoading, setIsLoading] = useState(false);
  const [isModelLoading, setIsModelLoading] = useState(false);
  const [modelLoadError, setModelLoadError] = useState<string | null>(null);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [progress, setProgress] = useState('');
  const [progressVal, setProgressVal] = useState(0);

  // RAG state for local models
  const [enableRAG, setEnableRAG] = useState(true);
  const [isRAGLoading, setIsRAGLoading] = useState(false);
  const [_lastRAGContexts, setLastRAGContexts] = useState<RAGContextItem[]>([]);

  // Settings
  const [settings] = useState<ChatSettings>(DEFAULT_SETTINGS);

  // Refs
  const engineRef = useRef<MLCEngine | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);
  const isHydratedRef = useRef(false);
  const hasRestoredThreadRef = useRef(false);
  const lastStreamedContentRef = useRef<string>('');

  // Scroll state
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Citation panel state
  const [isCitationPanelOpen, setIsCitationPanelOpen] = useState(false);
  const [citationPanelCitations, setCitationPanelCitations] = useState<
    Citation[]
  >([]);
  const [activeCitationId, setActiveCitationId] = useState<string | undefined>(
    undefined
  );

  // Auth
  const { isAuthenticated, token } = useAuthStore();

  // Get currentThreadId and setCurrentThread from chat store to sync with sidebar
  const currentThreadIdFromStore = useChatStore(
    (state) => state.currentThreadId
  );
  const setCurrentThread = useChatStore((state) => state.setCurrentThread);
  const storeMessages = useChatStore((state) => state.messages);
  const addMessageToStore = useChatStore((state) => state.addMessageToStore);

  // Streaming state from store (for cloud model SSE streaming)
  const storeStreamMessage = useChatStore((state) => state.streamMessage);
  const storeStopStreaming = useChatStore((state) => state.stopStreaming);
  const storeIsStreaming = useChatStore((state) => state.isStreaming);
  const storeStreamingContent = useChatStore((state) => state.streamingContent);
  const _storeStreamingCitations = useChatStore(
    (state) => state.streamingCitations
  );
  const currentModel = AVAILABLE_MODELS.find((m) => m.id === selectedModel);
  const activeThreadId = currentThreadIdFromStore || activeConversationId;
  const displayedMessages = selectDisplayedMessages({
    localMessages: messages,
    storeMessages: activeThreadId ? storeMessages[activeThreadId] || [] : [],
  });

  // Map DB messages to UI messages
  const mapDbMessageToUiMessage = useCallback(
    (dbMsg: DBChatMessage): Message => {
      return {
        id: dbMsg.id,
        role: dbMsg.role === MessageRole.USER ? 'user' : 'assistant',
        content: dbMsg.content,
        timestamp: new Date(dbMsg.created_at).getTime(),
        // Use normalizeCitation to handle both DB and API citation formats
        citations: dbMsg.citations?.map(normalizeCitation),
      };
    },
    []
  );

  // Capture a stable timestamp when streaming begins
  const streamingTimestampRef = useRef(Date.now());
  useEffect(() => {
    if (storeIsStreaming) {
      streamingTimestampRef.current = Date.now();
    }
  }, [storeIsStreaming]);

  // Track streaming content in a ref for post-stream fallback
  useEffect(() => {
    if (storeStreamingContent) {
      lastStreamedContentRef.current = storeStreamingContent;
    }
  }, [storeStreamingContent]);

  useEffect(() => {
    if (!activeThreadId) {
      return;
    }

    const activeStoreMessages = storeMessages[activeThreadId] || [];
    if (activeStoreMessages.length === 0) {
      return;
    }

    setConversations((prev) =>
      syncConversationMessagesWithStore(
        prev,
        activeThreadId,
        activeStoreMessages
      )
    );
  }, [activeThreadId, storeMessages]);

  const searchParams = useSearchParams();
  const router = useRouter();

  // Reset refs when user changes (logout/login)
  useEffect(() => {
    if (!isAuthenticated) {
      hasRestoredThreadRef.current = false;
      isHydratedRef.current = false;
    }
  }, [isAuthenticated]);

  // Listen for populate-chat-input events from Follow-up Suggestions
  useEffect(() => {
    const handlePopulateChatInput = (event: CustomEvent<string>) => {
      if (event.detail) {
        setInput(event.detail);
        // Focus the textarea after populating
        chatInputRef.current?.focus();
      }
    };

    window.addEventListener(
      'populate-chat-input',
      handlePopulateChatInput as EventListener
    );
    return () => {
      window.removeEventListener(
        'populate-chat-input',
        handlePopulateChatInput as EventListener
      );
    };
  }, []);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isAuthenticated && !isInitializing) {
      const timer = setTimeout(() => {
        router.push('/login');
      }, 1500); // Short delay to show the "Redirecting..." state
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, isInitializing, router]);

  // Handle thread switching from URL query param or sessionStorage (when navigating from sidebar)
  // This runs whenever we're on /chat and checks for pending thread switch
  useEffect(() => {
    if (conversations.length === 0 || isInitializing) {
      return;
    }

    // Check URL query param first (most reliable), then sessionStorage
    const threadFromUrl = searchParams.get('thread');
    let threadFromStorage: string | null = null;
    try {
      const raw = sessionStorage.getItem('activeThreadId');
      if (raw) {
        const parsed = JSON.parse(raw);
        // Expire entries older than 30 seconds to prevent stale state
        if (parsed.threadId && Date.now() - parsed.timestamp < 30_000) {
          threadFromStorage = parsed.threadId;
        } else {
          sessionStorage.removeItem('activeThreadId');
        }
      }
    } catch {
      // Handle legacy plain-string format gracefully
      threadFromStorage = sessionStorage.getItem('activeThreadId');
    }
    const targetThreadId = threadFromUrl || threadFromStorage;

    if (targetThreadId) {
      console.log(
        '[Chat] Thread switch requested:',
        targetThreadId,
        'source:',
        threadFromUrl ? 'URL' : 'sessionStorage'
      );
      const targetConv = conversations.find((c) => c.id === targetThreadId);

      if (targetConv) {
        if (targetConv.id !== activeConversationId) {
          setActiveConversationId(targetConv.id);
          setMessages(targetConv.messages);
          // Also update the Zustand store so sidebar highlights correctly
          setCurrentThread(targetConv.id);
          console.log('[Chat] Switched to thread:', targetConv.title);
        }
        // Clear sessionStorage (URL param stays for bookmarking/sharing)
        sessionStorage.removeItem('activeThreadId');
        return;
      }

      console.log(
        '[Chat] Thread not found in conversations, fetching detail:',
        targetThreadId
      );

      let cancelled = false;

      (async () => {
        try {
          const threadDetail = await workspaceService.getThread(targetThreadId);
          if (cancelled) return;

          const uiMessages = threadDetail.messages.map(mapDbMessageToUiMessage);
          setConversations((prev) =>
            upsertConversationFromThreadDetail(
              prev,
              threadDetail,
              mapDbMessageToUiMessage
            )
          );
          setActiveConversationId(threadDetail.id);
          setMessages(uiMessages);
          setCurrentThread(threadDetail.id);
        } catch (error) {
          if (!cancelled) {
            console.error('[Chat] Failed to fetch requested thread:', error);
          }
        } finally {
          if (!cancelled) {
            sessionStorage.removeItem('activeThreadId');
          }
        }
      })();

      return () => {
        cancelled = true;
      };
    }
  }, [
    searchParams,
    conversations,
    isInitializing,
    activeConversationId,
    mapDbMessageToUiMessage,
    setCurrentThread,
  ]);

  // Sync with Zustand store's currentThreadId (triggered by sidebar clicks via useChatPersistence)
  // This ensures the chat page updates when sidebar selection changes the store
  useEffect(() => {
    if (
      !currentThreadIdFromStore ||
      isInitializing ||
      conversations.length === 0
    ) {
      return;
    }

    // Only update if the store's thread is different from our local state
    if (currentThreadIdFromStore !== activeConversationId) {
      console.log(
        '[Chat] Store thread changed:',
        currentThreadIdFromStore,
        '(local:',
        activeConversationId,
        ')'
      );

      // Try to find the thread in local conversations first
      const targetConv = conversations.find(
        (c) => c.id === currentThreadIdFromStore
      );

      if (targetConv) {
        console.log(
          '[Chat] Found thread in local state, syncing:',
          targetConv.title
        );
        setActiveConversationId(targetConv.id);
        setMessages(targetConv.messages);
      } else {
        // Thread not in local conversations, try to load from store messages
        const messagesFromStore = storeMessages[currentThreadIdFromStore];
        if (messagesFromStore && messagesFromStore.length > 0) {
          console.log(
            '[Chat] Loading messages from store for thread:',
            currentThreadIdFromStore
          );
          setActiveConversationId(currentThreadIdFromStore);
          // Map store messages to UI format using normalizeCitation
          setMessages(
            messagesFromStore.map((dbMsg) => ({
              id: dbMsg.id,
              role:
                dbMsg.role === MessageRole.USER
                  ? ('user' as const)
                  : ('assistant' as const),
              content: dbMsg.content,
              timestamp: new Date(dbMsg.created_at).getTime(),
              citations: dbMsg.citations?.map(normalizeCitation),
            }))
          );
        } else {
          // Thread exists but no messages yet - still switch to it
          console.log(
            '[Chat] Switching to thread with no messages:',
            currentThreadIdFromStore
          );
          setActiveConversationId(currentThreadIdFromStore);
          setMessages([]);
        }
      }
    }
  }, [
    currentThreadIdFromStore,
    conversations,
    isInitializing,
    activeConversationId,
    storeMessages,
  ]);

  // Load threads and messages from database
  const loadThreadsFromDb = useCallback(
    async (conversationId: string, _isRetry = false): Promise<boolean> => {
      try {
        console.log(
          '[Chat] Loading threads from database for conversation:',
          conversationId
        );
        const threadResponse = await workspaceService.listThreads(
          conversationId,
          { limit: 50 }
        );

        // Map threads to UI conversations
        // Map threads without loading messages (lazy-loaded on selection)
        const uiConversations: Conversation[] = threadResponse.threads.map(
          (thread) => ({
            id: thread.id,
            title: thread.title || 'New Chat',
            messages: [],
            createdAt: new Date(thread.created_at).getTime(),
            updatedAt: new Date(thread.updated_at).getTime(),
            threadId: thread.id,
            conversationId: conversationId,
            previewText: thread.summary || undefined,
            messageCount: thread.message_count,
          })
        );

        setConversations(uiConversations);
        console.log(
          '[Chat] Loaded',
          uiConversations.length,
          'threads from database'
        );

        // Restore active thread - check sessionStorage first, then use first conversation
        if (uiConversations.length > 0) {
          // Only set state if we haven't already done so
          // This prevents React Strict Mode double-execution from overwriting correct state
          if (hasRestoredThreadRef.current) {
            console.log(
              '[Chat] Skipping thread restore (already done, preventing Strict Mode duplicate)'
            );
            return true;
          }

          let selectedConv = uiConversations[0];
          let savedThreadId: string | null = null;
          try {
            const raw = sessionStorage.getItem('activeThreadId');
            if (raw) {
              const parsed = JSON.parse(raw);
              if (parsed.threadId && Date.now() - parsed.timestamp < 30_000) {
                savedThreadId = parsed.threadId;
              }
            }
          } catch {
            // Handle legacy plain-string format
            savedThreadId = sessionStorage.getItem('activeThreadId');
          }

          if (savedThreadId) {
            const savedConv = uiConversations.find(
              (c) => c.id === savedThreadId
            );
            if (savedConv) {
              selectedConv = savedConv;
              console.log(
                '[Chat] Restored thread from sessionStorage:',
                savedConv.title
              );
            }
          }
          // Always clear sessionStorage after reading
          sessionStorage.removeItem('activeThreadId');

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
          console.warn(
            '[Chat] Conversation not found (404) - clearing stale data'
          );
          // Clear stale localStorage data
          if (typeof window !== 'undefined') {
            localStorage.removeItem('default-workspace-id');
            localStorage.removeItem('default-conversation-id');
          }
          return false; // Signal to caller to retry with fresh data
        }

        throw error;
      }
    },
    [mapDbMessageToUiMessage, setCurrentThread]
  );

  // Initialize workspace and conversation from database
  useEffect(() => {
    const initializeFromDb = async () => {
      if (!isAuthenticated || !token) {
        console.log(
          '[Chat] Not authenticated, skipping database initialization'
        );
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
        const conv = await workspaceService.getOrCreateDefaultConversation(
          ws.id
        );
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
            setInitError(
              'Failed to create new chat session. Please refresh the page.'
            );
            setIsInitializing(false);
            return;
          }
        }

        setInitError(
          error instanceof Error ? error.message : 'Failed to load chat data'
        );
      } finally {
        setIsInitializing(false);
      }
    };

    initializeFromDb();
  }, [isAuthenticated, token, loadThreadsFromDb]);

  // Load messages when active conversation changes (lazy-load from API)
  useEffect(() => {
    if (!activeConversationId) {
      setIsLoadingMessages(false);
      return;
    }
    const conv = conversations.find((c) => c.id === activeConversationId);
    if (!conv) {
      setIsLoadingMessages(false);
      return;
    }

    // If messages already loaded (cached), use them directly
    if (conv.messages.length > 0) {
      setMessages(conv.messages);
      setIsLoadingMessages(false);
      return;
    }

    // Lazy-load messages for this thread
    let cancelled = false;
    setIsLoadingMessages(true);
    (async () => {
      try {
        const msgResponse = await workspaceService.listMessages(
          activeConversationId,
          { limit: 100 }
        );
        if (cancelled) return;
        const uiMessages = msgResponse.messages.map(mapDbMessageToUiMessage);
        // Update conversation cache so subsequent switches are instant
        setConversations((prev) =>
          prev.map((c) =>
            c.id === activeConversationId ? { ...c, messages: uiMessages } : c
          )
        );
        setMessages(uiMessages);
      } catch (err) {
        if (!cancelled) {
          console.error('[Chat] Failed to load messages:', err);
        }
      } finally {
        if (!cancelled) {
          setIsLoadingMessages(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only trigger on thread selection, not conversation updates
  }, [activeConversationId, mapDbMessageToUiMessage]);

  // Auto-scroll when new messages arrive or streaming content updates
  useEffect(() => {
    if (!showScrollButton) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [displayedMessages, storeStreamingContent, showScrollButton]);

  // Handle scroll to detect if user scrolled up
  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const { scrollTop, scrollHeight, clientHeight } = container;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    setShowScrollButton(!isNearBottom && displayedMessages.length > 0);
  }, [displayedMessages.length]);

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
    setModelLoadError(null);
    try {
      if (!engineRef.current) {
        const { CreateMLCEngine } = await import('@mlc-ai/web-llm');
        engineRef.current = await CreateMLCEngine(modelId, {
          initProgressCallback,
        });
      } else {
        await engineRef.current.reload(modelId);
      }
    } catch (err) {
      console.error('Failed to load model:', err);
      setModelLoadError(
        err instanceof Error ? err.message : 'Failed to load model'
      );
    } finally {
      setIsModelLoading(false);
    }
  };

  // Model change handler
  const handleModelChange = async (modelId: string) => {
    setSelectedModel(modelId);
    setModelLoadError(null);
    await loadModel(modelId);
  };

  // Send message
  const handleSubmit = async () => {
    if (
      !input.trim() ||
      isLoading ||
      storeIsStreaming ||
      isModelLoading ||
      !selectedModel
    )
      return;

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
        console.log(
          '[Chat] Creating new thread in database with title:',
          dynamicTitle
        );
        const newThread = await workspaceService.createThread(
          buildThreadCreateRequest({
            conversationId: dbConversation.id,
            title: dynamicTitle,
          })
        );

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
        setCurrentThread(newConv.id);
        setActiveThread(newThread);
        router.replace(getSelectedThreadUrl(newThread.id));
        console.log('[Chat] Created new thread:', newThread.id);
      } catch (error) {
        console.error('[Chat] Failed to create thread:', error);
        setIsLoading(false);
        return;
      }
    }

    // Save user message to database (skip for cloud models -- streaming endpoint persists it)
    if (currentThreadId && isAuthenticated && !isCloudModel) {
      try {
        const savedUserMessage = await workspaceService.createMessage({
          thread_id: currentThreadId,
          content: input.trim(),
          role: MessageRole.USER,
        });
        console.log('[Chat] Saved user message to database');
        // Sync to Zustand store so layout can see it
        addMessageToStore(currentThreadId, savedUserMessage);
      } catch (error) {
        console.error('[Chat] Failed to save user message:', error);
      }
    }

    try {
      let assistantMessage = '';

      if (isCloudModel) {
        // Use SSE streaming for cloud models (GPT-4o via Azure OpenAI)
        // streamMessage handles the full lifecycle: stream tokens, then loadMessages on completion.
        // The virtual streaming message is rendered in the message list via storeIsStreaming/storeStreamingContent.
        // IMPORTANT: streamMessage does NOT clear isStreaming/streamingContent on success —
        // we clear them here AFTER syncing local state to avoid a flash where the
        // virtual streaming message disappears before the final messages are displayed.
        console.log(
          '[Chat] Starting SSE stream for cloud model, thread:',
          currentThreadId
        );
        lastStreamedContentRef.current = '';
        await storeStreamMessage(
          input.trim(),
          currentThreadId || undefined,
          enableRAG
        );

        // After streaming completes, the store has refreshed messages via loadMessages.
        // Keep local fallback only if store messages failed to arrive.
        if (currentThreadId) {
          let updatedStoreMessages =
            useChatStore.getState().messages[currentThreadId] || [];
          if (updatedStoreMessages.length === 0) {
            // Retry after a short delay — loadMessages may still be propagating
            await new Promise((r) => setTimeout(r, STORE_PROPAGATION_DELAY_MS));
            updatedStoreMessages =
              useChatStore.getState().messages[currentThreadId] || [];
          }
          if (updatedStoreMessages.length === 0 && lastStreamedContentRef.current) {
            // Fallback: store loadMessages returned empty (e.g. network hiccup).
            // Construct the assistant message from captured streaming content.
            console.warn(
              '[Chat] Store messages empty after stream, using captured content fallback'
            );
            const fallbackMessages: Message[] = [
              ...newMessages,
              {
                role: 'assistant' as const,
                content: lastStreamedContentRef.current,
                timestamp: Date.now(),
              },
            ];
            setMessages(fallbackMessages);
            setConversations((prev) =>
              prev.map((conv) =>
                conv.id === currentConversationId
                  ? {
                      ...conv,
                      messages: fallbackMessages,
                      updatedAt: Date.now(),
                    }
                  : conv
              )
            );
          }
        }

        // NOW clear streaming state — the virtual message disappears only
        // after local messages are already set with the final response.
        storeStopStreaming();
        lastStreamedContentRef.current = '';
      } else {
        // Use local WebLLM engine for browser-based models
        let ragContexts: RAGContextItem[] = [];
        let systemPrompt = settings.systemPrompt;

        // Phase 2: Get model-aware configuration
        const modelSize = getModelSize(selectedModel);
        const ragConfig = getRAGConfigForModel(modelSize);
        console.log(`[RAG] Model size: ${modelSize}, Config:`, ragConfig);

        // Retrieve RAG context if enabled for local models
        if (enableRAG) {
          setIsRAGLoading(true);
          console.log('[RAG] Retrieving context for local model...');

          try {
            // Phase 2: Use model-aware RAG configuration
            const ragResult = await ragService.retrieve(input.trim(), {
              maxDocs: ragConfig.maxDocs,
              minScore: 0.05, // Low threshold to match cloud model behavior
              maxTokens: ragConfig.maxTokens,
            });

            if (ragResult && ragResult.contexts.length > 0) {
              ragContexts = ragResult.contexts;
              // Phase 2: Pass modelSize for adaptive prompt building
              systemPrompt = buildRAGSystemPrompt(
                settings.systemPrompt,
                ragContexts,
                modelSize
              );
              setLastRAGContexts(ragContexts);
              console.log(
                `[RAG] Retrieved ${ragContexts.length} contexts in ${ragResult.retrievalTimeMs.toFixed(0)}ms`
              );
            } else {
              console.log(
                '[RAG] No relevant context found, proceeding without RAG'
              );
            }
          } catch (error) {
            console.error(
              '[RAG] Retrieval failed, falling back to no-context mode:',
              error
            );
          } finally {
            setIsRAGLoading(false);
          }
        }

        // Debug: Log the system prompt to verify RAG context is included
        console.log('[RAG] System prompt length:', systemPrompt.length);
        console.log(
          '[RAG] System prompt preview:',
          systemPrompt.substring(0, 500) + '...'
        );

        // Phase 2: Trim conversation history based on model size
        const trimmedHistory = getModelAwareHistory(
          newMessages.map((m) => ({ role: m.role, content: m.content })),
          selectedModel
        );

        const response = await engineRef.current!.chat.completions.create({
          messages: [
            { role: 'system', content: systemPrompt },
            ...trimmedHistory,
          ],
          temperature: settings.temperature,
          max_tokens: settings.maxTokens,
          stream: true,
        });

        const allLocalModelCitations: Citation[] = ragContexts.map((ctx) => ({
          documentId: ctx.documentId,
          title: ctx.title,
          score: ctx.score,
          content: ctx.content,
          source: ctx.source || ctx.documentType,
        }));

        const allDbCitations: CitationCreate[] = ragContexts
          .filter((ctx) => ctx.documentId)
          .map((ctx) => ({
            document_id: ctx.documentId,
            document_title: ctx.title,
            document_type: ctx.documentType,
            snippet: ctx.content,
            score: ctx.score,
          }));

        // Handle streaming response
        for await (const chunk of response) {
          const delta = chunk.choices[0]?.delta?.content || '';
          assistantMessage += delta;
          const referencedStreamingCitations =
            getReferencedItemsByCitationIndex(
              assistantMessage,
              allLocalModelCitations
            );
          setMessages([
            ...newMessages,
            {
              role: 'assistant',
              content: assistantMessage,
              timestamp: Date.now(),
              citations:
                referencedStreamingCitations.length > 0
                  ? referencedStreamingCitations
                  : undefined,
            },
          ]);
        }

        const localModelCitations = getReferencedItemsByCitationIndex(
          assistantMessage,
          allLocalModelCitations
        );
        const dbCitations = getReferencedItemsByCitationIndex(
          assistantMessage,
          allDbCitations
        );

        // Save assistant message to database (for local models too)
        if (currentThreadId && isAuthenticated) {
          try {
            const savedMessage = await workspaceService.createMessage({
              thread_id: currentThreadId,
              content: assistantMessage,
              role: MessageRole.ASSISTANT,
              citations: dbCitations.length > 0 ? dbCitations : undefined,
            });
            console.log(
              '[Chat] Saved local model response to database with',
              dbCitations.length,
              'citations'
            );
            // Sync to Zustand store so layout's citation panel can read it
            addMessageToStore(currentThreadId, savedMessage);

            // Persist citations through citation service for better querying
            if (savedMessage?.id && ragContexts.length > 0) {
              try {
                const citationIds = await ragService.persistCitations(
                  savedMessage.id,
                  assistantMessage,
                  ragContexts
                );
                console.log(
                  `[RAG] Persisted ${citationIds.length} citations for message ${savedMessage.id}`
                );
              } catch (citError) {
                console.error('[RAG] Failed to persist citations:', citError);
              }
            }
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
            citations:
              localModelCitations.length > 0 ? localModelCitations : undefined,
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
      const errorMessage =
        'Error: ' +
        (err instanceof Error ? err.message : 'Failed to get response');

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
      // Safety: ensure streaming state is always cleared.
      // On success, storeStopStreaming() was already called above.
      // On error, the catch in streamMessage clears it. But if the sync
      // code in handleSubmit itself throws, we need this safety net.
      if (useChatStore.getState().isStreaming) {
        storeStopStreaming();
      }
    }
  };

  const handleStop = () => {
    setIsLoading(false);
    // Also stop SSE streaming if active (for cloud models)
    if (storeIsStreaming) {
      storeStopStreaming();
    }
  };

  const handlePromptSelect = (prompt: string) => {
    setInput(prompt);
  };

  return (
    <div className="flex h-full w-full overflow-hidden bg-[var(--terminal-bg)]">
      {/* Chat Sidebar */}
      <div className="hidden md:block h-full shrink-0">
        <ChatSidebar
          conversations={conversations}
          activeId={activeConversationId}
          onSelect={(id) => {
            setActiveConversationId(id);
            setCurrentThread(id);
            router.push(getSelectedThreadUrl(id));
          }}
          onNew={() => {
            setActiveConversationId(null);
            setMessages([]);
            setCurrentThread(null);
            router.push(getNewChatUrl());
          }}
        />
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col relative h-full min-w-0 overflow-hidden">
        <ChatHeader currentWorkspace={_workspace} />

        {/* Model Loading Progress */}
        <AnimatePresence>
          {isModelLoading && (
            <ModelLoadingProgress
              progress={progress}
              progressVal={progressVal}
            />
          )}
        </AnimatePresence>

        {/* Model Load Error */}
        {modelLoadError && (
          <div
            className="mx-4 mt-2 px-3 py-2 rounded-lg border text-xs flex items-center gap-2"
            style={{
              borderColor: 'rgba(239, 68, 68, 0.3)',
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              color: '#ef4444',
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            <span>Model load failed: {modelLoadError}</span>
            <button
              onClick={() => setModelLoadError(null)}
              className="ml-auto opacity-60 hover:opacity-100"
              aria-label="Dismiss model error"
            >
              &times;
            </button>
          </div>
        )}

        {/* Messages Area Wrapper */}
        <div className="flex-1 relative min-h-0">
          <div
            ref={scrollContainerRef}
            onScroll={handleScroll}
            className="h-full overflow-y-auto terminal-scrollbar"
          >
            {/* Authentication Required State */}
            {!isAuthenticated ? (
              <div className="h-full flex flex-col items-center justify-center p-8">
                <div className="text-center">
                  <Loader2 className="w-8 h-8 text-[var(--amber-gold)] animate-spin mx-auto mb-4" />
                  <p className="text-sm font-mono text-[var(--terminal-text-muted)] mt-2">
                    Authentication required. Redirecting...
                  </p>
                </div>
              </div>
            ) : isInitializing ? (
              /* Loading State */
              <div className="h-full flex flex-col items-center justify-center p-8">
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-center"
                >
                  <div className="relative w-12 h-12 mx-auto mb-6">
                    <Loader2 className="w-12 h-12 text-[var(--phosphor-green)] animate-spin" />
                  </div>
                  <h2
                    className="text-sm text-[var(--phosphor-green)] mb-2 tracking-widest"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    INITIALIZING...
                  </h2>
                </motion.div>
              </div>
            ) : initError ? (
              /* Error State */
              <div className="h-full flex flex-col items-center justify-center p-8">
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="text-center max-w-md"
                >
                  <div className="relative w-16 h-16 mx-auto mb-6">
                    <div className="absolute inset-0 rounded-full bg-[var(--error-red)]/10" />
                    <div className="absolute inset-2 rounded-full border border-[var(--error-red)]/30 flex items-center justify-center">
                      <Activity className="w-6 h-6 text-[var(--error-red)]" />
                    </div>
                  </div>
                  <h2
                    className="text-lg text-[var(--error-red)] mb-3"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    CONNECTION ERROR
                  </h2>
                  <p
                    className="text-xs text-[var(--terminal-text-muted)] mb-6 p-3 rounded bg-[var(--error-red)]/5 border border-[var(--error-red)]/10"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    {initError}
                  </p>
                  <button
                    onClick={() => window.location.reload()}
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[var(--terminal-surface)] border border-[var(--terminal-border)] text-[var(--terminal-text)] text-xs font-medium hover:border-[var(--phosphor-green)]/30 transition-all"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    <Activity className="w-3.5 h-3.5" />
                    RETRY CONNECTION
                  </button>
                </motion.div>
              </div>
            ) : isLoadingMessages ? (
              /* Loading Messages State */
              <div className="h-full flex flex-col items-center justify-center p-8">
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-center"
                >
                  <Loader2 className="w-8 h-8 text-[var(--phosphor-green)] animate-spin mx-auto mb-4" />
                  <p
                    className="text-xs text-[var(--terminal-text-muted)] tracking-wider"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    LOADING MESSAGES...
                  </p>
                </motion.div>
              </div>
            ) : displayedMessages.length === 0 && !storeIsStreaming ? (
              <WelcomeState
                onPromptSelect={handlePromptSelect}
                selectedModel={selectedModel}
              />
            ) : (
              <div className="max-w-4xl mx-auto pt-4 px-4 pb-6">
                <AnimatePresence>
                  {displayedMessages.map((message, index) => (
                    <motion.div
                      key={message.id || `msg-${index}`}
                      initial={{ opacity: 0, y: 20, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, transition: { duration: 0.2 } }}
                      transition={{
                        duration: 0.4,
                        delay: Math.min(index * 0.03, 0.3),
                        ease: [0.25, 0.46, 0.45, 0.94],
                      }}
                    >
                      <TerminalChatBubble
                        message={message}
                        index={index}
                        modelName={
                          message.role === 'assistant'
                            ? currentModel?.name
                            : undefined
                        }
                        isTyping={
                          index === displayedMessages.length - 1 &&
                          isLoading &&
                          !storeIsStreaming &&
                          message.role === 'assistant'
                        }
                        onCitationClick={(citations, clickedCitation) => {
                          setCitationPanelCitations(citations);
                          setActiveCitationId(clickedCitation.documentId);
                          setIsCitationPanelOpen(true);
                        }}
                      />
                    </motion.div>
                  ))}

                  {/* Virtual streaming assistant message (shown during SSE streaming) */}
                  {storeIsStreaming && (
                    <motion.div
                      key="streaming-message"
                      initial={{ opacity: 0, y: 20, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{
                        opacity: 0,
                        y: -10,
                        transition: { duration: 0.2 },
                      }}
                      transition={{ duration: 0.3 }}
                    >
                      <TerminalChatBubble
                        message={{
                          role: 'assistant',
                          content: '',
                          timestamp: streamingTimestampRef.current,
                        }}
                        index={displayedMessages.length}
                        modelName={currentModel?.name}
                        isStreaming={true}
                        streamingContent={storeStreamingContent}
                        onCitationClick={(citations, clickedCitation) => {
                          setCitationPanelCitations(citations);
                          setActiveCitationId(clickedCitation.documentId);
                          setIsCitationPanelOpen(true);
                        }}
                      />
                    </motion.div>
                  )}
                </AnimatePresence>
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Scroll to bottom button - Absolute positioned within wrapper */}
          <AnimatePresence>
            {showScrollButton && (
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
                <motion.button
                  initial={{ opacity: 0, y: 10, scale: 0.9 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 10, scale: 0.9 }}
                  onClick={scrollToBottom}
                  className="flex items-center gap-2 px-4 py-2 rounded-full bg-[var(--phosphor-green)] text-[var(--terminal-bg)] text-xs font-bold shadow-[0_0_20px_var(--phosphor-green-glow)] hover:shadow-[0_0_30px_var(--phosphor-green-glow)] transition-all pointer-events-auto border border-[var(--terminal-bg)]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  <ArrowDown className="w-4 h-4" />
                  <span className="hidden sm:inline tracking-wider">
                    NEW MESSAGES
                  </span>
                </motion.button>
              </div>
            )}
          </AnimatePresence>
        </div>

        {/* Input Area */}
        <ChatInput
          value={input}
          onChange={setInput}
          onSubmit={handleSubmit}
          onStop={handleStop}
          isLoading={isLoading || storeIsStreaming}
          isModelLoading={isModelLoading}
          selectedModel={selectedModel}
          models={AVAILABLE_MODELS}
          onModelChange={handleModelChange}
          enableRAG={enableRAG}
          onRAGToggle={setEnableRAG}
          isRAGLoading={isRAGLoading}
          inputRef={chatInputRef}
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
    </div>
  );
}

// Wrapper component with Suspense boundary for useSearchParams
export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex-1 flex flex-col items-center justify-center p-8">
          <div className="text-center">
            <Loader2 className="w-12 h-12 text-[var(--phosphor-green)] animate-spin mx-auto mb-4" />
            <p className="text-sm font-mono text-[var(--terminal-text-muted)]">
              Loading chat...
            </p>
          </div>
        </div>
      }
    >
      <ChatPageContent />
    </Suspense>
  );
}
