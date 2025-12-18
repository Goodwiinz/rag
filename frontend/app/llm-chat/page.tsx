'use client';

import { SimpleLayout } from '@/components/layout/SimpleLayout';
import { Button } from '@/components/ui/button';
import {
  MessageBubble,
  ChatInput,
  ModelSelector,
  ChatSettingsPanel,
  ConversationSidebar,
  ChatAnalytics,
  Model,
  ChatSettings,
  Conversation,
  ChatMetrics,
} from '@/components/chat';
import { CreateMLCEngine, InitProgressReport, MLCEngine } from "@mlc-ai/web-llm";
import { AnimatePresence, motion } from 'framer-motion';
import {
  Bot,
  Check,
  MessageSquare,
  Plus,
  Settings,
  Sparkles,
  BarChart3,
  Menu,
  X,
  Zap,
  Clock,
  Cpu,
  Shield,
} from 'lucide-react';
import { useEffect, useRef, useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { getAnalytics } from '@/lib/analytics';

// Available models
const AVAILABLE_MODELS: Model[] = [
  {
    id: 'Llama-3.2-1B-Instruct-q4f32_1-MLC',
    name: 'Llama 3.2 1B',
    description: 'Efficient model for quick responses',
    size: '1B',
    parameters: '1.2B',
    ram: '~2GB',
    speed: 'Very Fast',
    accuracy: 78,
    features: ['Text Generation', 'Q&A', 'Summarization'],
    tags: ['lightweight', 'fast', 'efficient'],
    isRecommended: true,
    benchmarks: { reasoning: 72, coding: 65, math: 70, language: 82 }
  },
  {
    id: 'Llama-3.2-3B-Instruct-q4f32_1-MLC',
    name: 'Llama 3.2 3B',
    description: 'Balanced model for quality and speed',
    size: '3B',
    parameters: '3.2B',
    ram: '~4GB',
    speed: 'Fast',
    accuracy: 84,
    features: ['Text Generation', 'Complex Q&A', 'Reasoning', 'Coding'],
    tags: ['balanced', 'versatile', 'popular'],
    isRecommended: true,
    isFeatured: true,
    benchmarks: { reasoning: 81, coding: 78, math: 79, language: 88 }
  },
  {
    id: 'gemma-2-2b-it-q4f16_1-MLC',
    name: 'Gemma 2 2B',
    description: "Google's efficient model with strong multilingual capabilities",
    size: '2B',
    parameters: '2.6B',
    ram: '~3GB',
    speed: 'Fast',
    accuracy: 82,
    features: ['Text Generation', 'Multilingual', 'Coding'],
    tags: ['multilingual', 'google', 'efficient'],
    benchmarks: { reasoning: 79, coding: 80, math: 76, language: 91 }
  },
  {
    id: 'Phi-3.5-mini-instruct-q4f16_1-MLC',
    name: 'Phi 3.5 Mini',
    description: "Microsoft's compact model optimized for instruction following",
    size: '3.8B',
    parameters: '3.8B',
    ram: '~4GB',
    speed: 'Medium',
    accuracy: 86,
    features: ['Instruction Following', 'Reasoning', 'Code Generation'],
    tags: ['microsoft', 'instruction-tuned', 'reliable'],
    benchmarks: { reasoning: 85, coding: 83, math: 82, language: 87 }
  },
  {
    id: 'Qwen2-1.5B-Instruct-q4f16_1-MLC',
    name: 'Qwen2 1.5B',
    description: 'Alibaba\'s lightweight model with strong performance',
    size: '1.5B',
    parameters: '1.5B',
    ram: '~2GB',
    speed: 'Very Fast',
    accuracy: 80,
    features: ['Text Generation', 'Chinese & English', 'Q&A'],
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
  systemPrompt: 'You are a helpful AI assistant.',
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

// Storage key
const STORAGE_KEY = 'webllm-conversations-v2';
const METRICS_STORAGE_KEY = 'webllm-chat-metrics';

export default function EnhancedWebLLMChatPage() {
  // Core state
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState('');

  // Loading states
  const [isLoading, setIsLoading] = useState(false);
  const [isModelLoading, setIsModelLoading] = useState(false);
  const [progress, setProgress] = useState('');
  const [progressVal, setProgressVal] = useState(0);

  // UI state
  const [settings, setSettings] = useState<ChatSettings>(DEFAULT_SETTINGS);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [showQuickPrompts, setShowQuickPrompts] = useState(true);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [copiedMessageIndex, setCopiedMessageIndex] = useState<number | null>(null);

  // Refs
  const engine = useRef<MLCEngine | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Analytics state
  const [metrics, setMetrics] = useState<ChatMetrics>({
    totalMessages: 0,
    totalConversations: 0,
    averageMessagesPerConversation: 0,
    averageResponseTime: 0,
    totalTokensUsed: 0,
    userSatisfactionScore: 85,
    messageRegenerationRate: 15,
    conversationCompletionRate: 78,
    bookmarkRate: 12,
    shareRate: 8,
    fastestResponseTime: 1200,
    slowestResponseTime: 5400,
    averageTokensPerMessage: 156,
    modelAccuracy: 87,
    messagesByHour: {},
    messagesByDay: {},
    peakActivityHour: 14,
    mostActiveDay: 'Monday',
    modelUsage: {},
    topTopics: [
      { topic: 'Programming', count: 45, sentiment: 'positive' },
      { topic: 'Writing', count: 32, sentiment: 'positive' },
      { topic: 'Analysis', count: 28, sentiment: 'neutral' },
      { topic: 'Learning', count: 24, sentiment: 'positive' },
    ],
    estimatedCost: 0.45,
    costPerMessage: 0.0023,
    costByModel: {},
    errorRate: 2,
    commonErrors: [
      { error: 'Model loading timeout', count: 3 },
      { error: 'Network error', count: 1 },
    ],
  });

  // Quick prompts
  const QUICK_PROMPTS = [
    { title: 'Explain a concept', description: 'Get clear explanations of complex topics', text: 'Explain [topic] like I\'m 5 years old' },
    { title: 'Write code', description: 'Generate code snippets in any language', text: 'Write a [language] function that [does what]' },
    { title: 'Brainstorm ideas', description: 'Get creative ideas for your projects', text: 'Give me 10 ideas for [topic]' },
    { title: 'Summarize text', description: 'Create concise summaries', text: 'Summarize this text: [paste text]' },
  ];

  // Load conversations from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        setConversations(parsed);
      } catch (e) {
        console.error('Failed to parse conversations:', e);
      }
    }

    // Load metrics
    const metricsStored = localStorage.getItem(METRICS_STORAGE_KEY);
    if (metricsStored) {
      try {
        setMetrics(JSON.parse(metricsStored));
      } catch (e) {
        console.error('Failed to parse metrics:', e);
      }
    }
  }, []);

  // Save conversations to localStorage
  useEffect(() => {
    if (conversations.length > 0 && settings.autoSave) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    }
  }, [conversations, settings.autoSave]);

  // Save metrics
  useEffect(() => {
    localStorage.setItem(METRICS_STORAGE_KEY, JSON.stringify(metrics));
  }, [metrics]);

  // Load active conversation
  useEffect(() => {
    if (activeConversationId) {
      const conv = conversations.find(c => c.id === activeConversationId);
      if (conv) {
        setMessages(conv.messages);
        setSettings(prev => ({ ...prev, ...conv.settings }));
        setShowQuickPrompts(false);
      }
    }
  }, [activeConversationId, conversations]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Update analytics
  const updateAnalytics = useCallback((
    type: 'message' | 'conversation' | 'response_time',
    data?: any
  ) => {
    setMetrics(prev => {
      const updated = { ...prev };

      if (type === 'message') {
        updated.totalMessages += 1;
        const hour = new Date().getHours();
        updated.messagesByHour[hour] = (updated.messagesByHour[hour] || 0) + 1;
      } else if (type === 'conversation') {
        updated.totalConversations += 1;
        updated.averageMessagesPerConversation = updated.totalMessages / updated.totalConversations;
      } else if (type === 'response_time' && data) {
        const totalTime = prev.averageResponseTime * (prev.totalMessages - 1) + data.responseTime;
        updated.averageResponseTime = totalTime / prev.totalMessages;

        if (data.tokens) {
          updated.totalTokensUsed += data.tokens;
          updated.averageTokensPerMessage = updated.totalTokensUsed / updated.totalMessages;
        }

        // Update model usage
        if (selectedModel) {
          if (!updated.modelUsage[selectedModel]) {
            const model = AVAILABLE_MODELS.find(m => m.id === selectedModel);
            updated.modelUsage[selectedModel] = {
              name: model?.name || 'Unknown',
              usage: 0,
              avgResponseTime: data.responseTime,
              satisfactionScore: prev.userSatisfactionScore,
              tokensUsed: data.tokens,
            };
          }
          updated.modelUsage[selectedModel].usage += 1;
          updated.modelUsage[selectedModel].tokensUsed += data.tokens;
          updated.modelUsage[selectedModel].avgResponseTime =
            (updated.modelUsage[selectedModel].avgResponseTime + data.responseTime) / 2;

          // Update cost
          const cost = data.tokens * 0.000002; // $0.002 per 1k tokens
          updated.estimatedCost += cost;
          updated.costByModel[selectedModel] = (updated.costByModel[selectedModel] || 0) + cost;
        }
      }

      return updated;
    });
  }, [selectedModel]);

  // Model initialization
  const initProgressCallback = (report: InitProgressReport) => {
    setProgress(report.text);
    setProgressVal(report.progress);
  };

  const loadModel = async (modelId: string) => {
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
  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isLoading || isModelLoading || !selectedModel) return;

    if (!engine.current) {
      console.error("Engine not initialized. Please load a model first.");
      return;
    }

    // Track analytics
    try {
      const analytics = getAnalytics();
      analytics.trackChatMessage('user', 'llm', input.trim().length);
      analytics.trackFeatureUsage('llm_chat', 'message_sent', {
        model: selectedModel,
        messageLength: input.trim().length,
        isNewConversation: !activeConversationId
      });
    } catch (error) {
      // Analytics not initialized, silently ignore
    }

    const startTime = Date.now();
    const userMessage = {
      role: 'user' as const,
      content: input.trim(),
      timestamp: Date.now(),
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);
    setShowQuickPrompts(false);

    // Create new conversation if needed
    if (!activeConversationId) {
      const newConv: Conversation = {
        id: crypto.randomUUID(),
        title: input.trim().substring(0, 50),
        messages: newMessages,
        modelId: selectedModel,
        settings,
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      setConversations(prev => [newConv, ...prev]);
      setActiveConversationId(newConv.id);
      updateAnalytics('conversation');
    }

    updateAnalytics('message');

    try {
      let assistantMessage = '';
      const chunks = await engine.current.chat.completions.create({
        messages: [
          { role: 'system', content: settings.systemPrompt },
          ...newMessages.map(m => ({ role: m.role, content: m.content }))
        ],
        temperature: settings.temperature,
        max_tokens: settings.maxTokens,
        stream: settings.streamResponses,
      });

      for await (const chunk of chunks) {
        const delta = chunk.choices[0]?.delta?.content || '';
        assistantMessage += delta;
        setMessages([
          ...newMessages,
          {
            role: 'assistant' as const,
            content: assistantMessage,
            timestamp: Date.now(),
          }
        ]);
      }

      const responseTime = Date.now() - startTime;
      const tokens = assistantMessage.split(' ').length * 1.3; // Rough token estimation

      const finalMessages = [
        ...newMessages,
        {
          role: 'assistant' as const,
          content: assistantMessage,
          timestamp: Date.now(),
        }
      ];

      setMessages(finalMessages);
      updateActiveConversation(finalMessages);
      updateAnalytics('response_time', { responseTime, tokens });

      // Track analytics
      try {
        const analytics = getAnalytics();
        analytics.trackChatMessage('assistant', 'llm', assistantMessage.length);
        analytics.trackFeatureUsage('llm_chat', 'message_received', {
          model: selectedModel,
          responseLength: assistantMessage.length,
          responseTime,
        });
      } catch (error) {
        // Analytics not initialized, silently ignore
      }
    } catch (err) {
      console.error('Failed to send message:', err);
      // Track error
      try {
        const analytics = getAnalytics();
        analytics.trackError(err as Error, 'llm_chat_message');
      } catch (error) {
        // Analytics not initialized, silently ignore
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Update active conversation
  const updateActiveConversation = useCallback((newMessages: any[]) => {
    if (!activeConversationId) return;

    setConversations(prev =>
      prev.map(conv =>
        conv.id === activeConversationId
          ? { ...conv, messages: newMessages, settings, updatedAt: Date.now() }
          : conv
      )
    );
  }, [activeConversationId, settings]);

  // Model change handler
  const handleModelChange = async (modelId: string) => {
    setSelectedModel(modelId);
    await loadModel(modelId);
  };

  // Conversation handlers
  const createNewConversation = () => {
    setActiveConversationId(null);
    setMessages([]);
    setShowQuickPrompts(true);
  };

  const deleteConversation = (id: string) => {
    setConversations(prev => prev.filter(c => c.id !== id));
    if (activeConversationId === id) {
      setActiveConversationId(null);
      setMessages([]);
      setShowQuickPrompts(true);
    }
  };

  const renameConversation = (id: string, title: string) => {
    setConversations(prev =>
      prev.map(conv =>
        conv.id === id ? { ...conv, title, updatedAt: Date.now() } : conv
      )
    );
  };

  const toggleBookmark = (id: string) => {
    setConversations(prev =>
      prev.map(conv =>
        conv.id === id ? { ...conv, isBookmarked: !conv.isBookmarked } : conv
      )
    );
  };

  const archiveConversation = (id: string) => {
    setConversations(prev =>
      prev.map(conv =>
        conv.id === id ? { ...conv, isArchived: true } : conv
      )
    );
  };

  const shareConversation = (id: string) => {
    const conv = conversations.find(c => c.id === id);
    if (conv) {
      // Generate share URL (simplified)
      const shareUrl = `${window.location.origin}/chat/shared/${id}`;
      navigator.clipboard.writeText(shareUrl);
      alert('Share URL copied to clipboard!');
    }
  };

  const exportConversation = (id: string) => {
    const conv = conversations.find(c => c.id === id);
    if (conv) {
      const dataStr = JSON.stringify(conv, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });
      const url = URL.createObjectURL(dataBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `conversation-${conv.title}-${Date.now()}.json`;
      link.click();
      URL.revokeObjectURL(url);
    }
  };

  const duplicateConversation = (id: string) => {
    const conv = conversations.find(c => c.id === id);
    if (conv) {
      const duplicated: Conversation = {
        ...conv,
        id: crypto.randomUUID(),
        title: `${conv.title} (Copy)`,
        createdAt: Date.now(),
        updatedAt: Date.now(),
        shareUrl: undefined,
      };
      setConversations(prev => [duplicated, ...prev]);
    }
  };

  const tagConversation = (id: string, tags: string[]) => {
    setConversations(prev =>
      prev.map(conv =>
        conv.id === id ? { ...conv, tags, updatedAt: Date.now() } : conv
      )
    );
  };

  const moveConversation = (id: string, folderId?: string) => {
    setConversations(prev =>
      prev.map(conv =>
        conv.id === id ? { ...conv, folderId, updatedAt: Date.now() } : conv
      )
    );
  };

  // Message handlers
  const copyMessage = async (content: string, index: number) => {
    await navigator.clipboard.writeText(content);
    setCopiedMessageIndex(index);
    setTimeout(() => setCopiedMessageIndex(null), 2000);
  };

  const regenerateResponse = async () => {
    if (messages.length < 2 || !selectedModel) return;

    const messagesWithoutLast = messages.slice(0, -1);
    setMessages(messagesWithoutLast);
    setIsLoading(true);

    const startTime = Date.now();

    try {
      let assistantMessage = '';
      const chunks = await engine.current.chat.completions.create({
        messages: [
          { role: 'system', content: settings.systemPrompt },
          ...messagesWithoutLast.map(m => ({ role: m.role, content: m.content }))
        ],
        temperature: settings.temperature,
        max_tokens: settings.maxTokens,
        stream: settings.streamResponses,
      });

      for await (const chunk of chunks) {
        const delta = chunk.choices[0]?.delta?.content || '';
        assistantMessage += delta;
        setMessages([
          ...messagesWithoutLast,
          {
            role: 'assistant' as const,
            content: assistantMessage,
            timestamp: Date.now(),
          }
        ]);
      }

      const finalMessages = [
        ...messagesWithoutLast,
        {
          role: 'assistant' as const,
          content: assistantMessage,
          timestamp: Date.now(),
        }
      ];

      setMessages(finalMessages);
      updateActiveConversation(finalMessages);

      const responseTime = Date.now() - startTime;
      updateAnalytics('response_time', {
        responseTime,
        tokens: assistantMessage.split(' ').length * 1.3
      });
    } catch (err) {
      console.error('Failed to regenerate response:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReaction = (type: 'like' | 'dislike') => {
    // Update satisfaction score based on reactions
    setMetrics(prev => {
      const scoreChange = type === 'like' ? 2 : -1;
      const newScore = Math.max(0, Math.min(100, prev.userSatisfactionScore + scoreChange));
      return { ...prev, userSatisfactionScore: newScore };
    });
  };

  // File and voice handlers
  const handleFileUpload = (files: File[]) => {
    // Implement file upload logic
    console.log('Files uploaded:', files);
    // For now, just add a message about the file
    const fileMessage = {
      role: 'user' as const,
      content: `Uploaded ${files.length} file(s): ${files.map(f => f.name).join(', ')}`,
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, fileMessage]);
  };

  const handleVoiceRecord = (blob: Blob) => {
    // Implement voice recording logic
    console.log('Voice recorded:', blob);
    // For now, just add a placeholder
    const voiceMessage = {
      role: 'user' as const,
      content: '[Voice message - transcription pending]',
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, voiceMessage]);
  };

  const activeConversation = conversations.find(c => c.id === activeConversationId);
  const currentModel = AVAILABLE_MODELS.find(m => m.id === selectedModel);

  return (
    <SimpleLayout showHeader={true}>
      <div className="flex h-[calc(100vh-4rem)]">
        {/* Sidebar */}
        <AnimatePresence>
          {sidebarOpen && (
            <motion.div
              initial={{ x: -300 }}
              animate={{ x: 0 }}
              exit={{ x: -300 }}
              className="w-80 border-r bg-background"
            >
              <ConversationSidebar
                conversations={conversations}
                activeConversationId={activeConversationId || undefined}
                onConversationSelect={setActiveConversationId}
                onNewConversation={createNewConversation}
                onDeleteConversation={deleteConversation}
                onRenameConversation={renameConversation}
                onToggleBookmark={toggleBookmark}
                onArchiveConversation={archiveConversation}
                onShareConversation={shareConversation}
                onExportConversation={exportConversation}
                onDuplicateConversation={duplicateConversation}
                onTagConversation={tagConversation}
                onMoveConversation={moveConversation}
                isOpen={sidebarOpen}
                onToggle={() => setSidebarOpen(!sidebarOpen)}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col">
          {/* Toolbar */}
          <div className="flex items-center justify-between px-4 py-3 border-b bg-background/95 backdrop-blur">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSidebarOpen(!sidebarOpen)}
              >
                <Menu className="w-4 h-4" />
              </Button>

              <ModelSelector
                models={AVAILABLE_MODELS}
                selectedModelId={selectedModel}
                onModelChange={handleModelChange}
                isLoading={isModelLoading}
              />
            </div>

            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowAnalytics(!showAnalytics)}
              >
                <BarChart3 className="w-4 h-4" />
                <span className="hidden sm:inline ml-1">Analytics</span>
              </Button>

              <ChatSettingsPanel
                settings={settings}
                onSettingsChange={setSettings}
                isOpen={settingsOpen}
                onOpenChange={setSettingsOpen}
              />
            </div>
          </div>

          {/* Model Loading Progress */}
          {isModelLoading && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="px-4 py-3 bg-gradient-to-r from-orange-500/5 to-amber-500/5 border-b"
            >
              <div className="flex items-center gap-4 max-w-2xl mx-auto">
                <div className="relative">
                  <div className="w-5 h-5 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
                  <div className="absolute -inset-2 bg-orange-500/10 rounded-full animate-ping" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">Loading model...</p>
                  <p className="text-xs text-muted-foreground truncate">{progress}</p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-sm font-medium text-orange-600">
                    {Math.round(progressVal * 100)}%
                  </div>
                  <div className="w-32 h-2 bg-muted rounded-full overflow-hidden">
                    <motion.div
                      className="h-full bg-gradient-to-r from-orange-500 to-orange-600"
                      initial={{ width: 0 }}
                      animate={{ width: `${progressVal * 100}%` }}
                      transition={{ duration: 0.3 }}
                    />
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* Content Area */}
          <div className="flex-1 overflow-hidden">
            <AnimatePresence mode="wait">
              {showAnalytics ? (
                <motion.div
                  key="analytics"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="h-full overflow-auto p-6"
                >
                  <ChatAnalytics metrics={metrics} />
                </motion.div>
              ) : (
                <motion.div
                  key="chat"
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  className="h-full flex flex-col"
                >
                  {/* Messages Area */}
                  <div className="flex-1 overflow-auto">
                    <div className="max-w-4xl mx-auto px-6 py-8">
                      {/* Empty State */}
                      {messages.length === 0 && !selectedModel && (
                        <motion.div
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="flex flex-col items-center justify-center py-20 text-center"
                        >
                          <div className="relative">
                            <div className="absolute inset-0 bg-gradient-to-r from-orange-500/20 to-amber-500/20 rounded-full blur-3xl" />
                            <div className="relative w-32 h-32 bg-gradient-to-br from-orange-100 to-amber-100 rounded-full flex items-center justify-center border border-orange-200">
                              <Bot className="w-16 h-16 text-orange-500" />
                            </div>
                          </div>
                          <h2 className="mt-8 text-3xl font-bold tracking-tight">Welcome to Enhanced WebLLM Chat</h2>
                          <p className="mt-3 text-lg text-muted-foreground max-w-lg">
                            Experience next-generation AI chat with advanced features, markdown support, and real-time analytics
                          </p>
                          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl">
                            <div className="p-4 rounded-lg border bg-card">
                              <Sparkles className="w-8 h-8 text-orange-500 mb-2" />
                              <h3 className="font-semibold">Smart Responses</h3>
                              <p className="text-sm text-muted-foreground mt-1">
                                Get intelligent answers with context awareness
                              </p>
                            </div>
                            <div className="p-4 rounded-lg border bg-card">
                              <Zap className="w-8 h-8 text-blue-500 mb-2" />
                              <h3 className="font-semibold">Lightning Fast</h3>
                              <p className="text-sm text-muted-foreground mt-1">
                                Models run directly in your browser
                              </p>
                            </div>
                            <div className="p-4 rounded-lg border bg-card">
                              <Shield className="w-8 h-8 text-green-500 mb-2" />
                              <h3 className="font-semibold">Private & Secure</h3>
                              <p className="text-sm text-muted-foreground mt-1">
                                Your data never leaves your device
                              </p>
                            </div>
                          </div>
                        </motion.div>
                      )}

                      {/* Model Ready State */}
                      {messages.length === 0 && selectedModel && !isModelLoading && (
                        <motion.div
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="flex flex-col items-center justify-center py-20 text-center"
                        >
                          <div className="relative">
                            <div className="absolute inset-0 bg-green-500/10 rounded-full blur-2xl" />
                            <div className="relative w-24 h-24 bg-gradient-to-br from-green-500/10 to-emerald-500/10 rounded-full flex items-center justify-center border border-green-500/20">
                              <Check className="w-12 h-12 text-green-600" />
                            </div>
                          </div>
                          <h2 className="mt-8 text-2xl font-bold">Model Ready</h2>
                          <p className="mt-2 text-muted-foreground">
                            Using <span className="font-medium text-foreground">
                              {currentModel?.name}
                            </span>
                          </p>
                          <p className="text-sm text-muted-foreground mt-1">
                            Type a message below to start the conversation
                          </p>
                        </motion.div>
                      )}

                      {/* Quick Prompts */}
                      {messages.length === 0 && selectedModel && !isModelLoading && showQuickPrompts && (
                        <motion.div
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: 0.1 }}
                          className="mb-8"
                        >
                          <h3 className="text-lg font-medium mb-4 text-center">Try these prompts</h3>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {QUICK_PROMPTS.map((prompt, idx) => (
                              <motion.button
                                key={idx}
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ delay: idx * 0.1 }}
                                whileHover={{ scale: 1.02 }}
                                whileTap={{ scale: 0.98 }}
                                className="p-4 text-left rounded-lg border bg-card hover:bg-accent hover:shadow-md transition-all"
                                onClick={() => setInput(prompt.text)}
                              >
                                <p className="font-medium">{prompt.title}</p>
                                <p className="text-sm text-muted-foreground mt-0.5">
                                  {prompt.description}
                                </p>
                              </motion.button>
                            ))}
                          </div>
                        </motion.div>
                      )}

                      {/* Messages */}
                      <AnimatePresence>
                        {messages.map((message, idx) => (
                          <MessageBubble
                            key={idx}
                            message={message}
                            isLast={idx === messages.length - 1}
                            isTyping={idx === messages.length - 1 && isLoading}
                            isCopied={copiedMessageIndex === idx}
                            onCopy={copyMessage}
                            onRegenerate={regenerateResponse}
                            onReaction={handleReaction}
                            modelInfo={message.role === 'assistant' && currentModel ? {
                              name: currentModel.name,
                              responseTime: 2000, // Would be tracked
                              tokens: Math.round(message.content.split(' ').length * 1.3),
                            } : undefined}
                          />
                        ))}
                      </AnimatePresence>

                      <div ref={messagesEndRef} />
                    </div>
                  </div>

                  {/* Input Area */}
                  <div className="border-t bg-background/95 backdrop-blur p-4">
                    <div className="max-w-4xl mx-auto">
                      <ChatInput
                        value={input}
                        onChange={setInput}
                        onSubmit={handleSubmit}
                        onStop={() => setIsLoading(false)}
                        isLoading={isLoading}
                        disabled={!selectedModel || isLoading || isModelLoading}
                        placeholder={
                          !selectedModel
                            ? "Select a model to start chatting..."
                            : "Type your message... (Enter to send, Shift+Enter for new line)"
                        }
                        showWordCount={true}
                        showToolbar={true}
                        allowFileUpload={true}
                        allowVoiceInput={true}
                        onFileUpload={handleFileUpload}
                        onVoiceRecord={handleVoiceRecord}
                        maxLength={4000}
                      />

                      {selectedModel && (
                        <div className="mt-2 text-xs text-center text-muted-foreground">
                          Powered by {currentModel?.name} • Responses are generated locally in your browser
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </SimpleLayout>
  );
}