'use client';

import { SimpleLayout } from '@/components/layout/SimpleLayout';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Slider } from '@/components/ui/slider';
import { Textarea } from '@/components/ui/textarea';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import { Switch } from '@/components/ui/switch';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { CreateMLCEngine, InitProgressReport, MLCEngine } from "@mlc-ai/web-llm";
import { AnimatePresence, motion } from 'framer-motion';
import {
    Bot,
    Check,
    ChevronDown,
    Copy,
    Loader2,
    MessageSquare,
    Plus,
    Send,
    Settings,
    Sparkles,
    Square,
    Trash2,
    User,
    Cpu,
    Zap,
    Clock,
    RefreshCw
} from 'lucide-react';
import { useEffect, useRef, useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { getAnalytics } from '@/lib/analytics';

const AVAILABLE_MODELS = [
  {
    id: 'Llama-3.2-1B-Instruct-q4f32_1-MLC',
    name: 'Llama 3.2 1B',
    size: '1B',
    description: 'Efficient model for quick responses',
    ram: '~2GB',
    speed: 'Fast'
  },
  {
    id: 'Llama-3.2-3B-Instruct-q4f32_1-MLC',
    name: 'Llama 3.2 3B',
    size: '3B',
    description: 'Balanced model for quality and speed',
    ram: '~4GB',
    speed: 'Medium'
  },
  {
    id: 'gemma-2-2b-it-q4f16_1-MLC',
    name: 'Gemma 2 2B',
    size: '2B',
    description: 'Google\'s efficient model',
    ram: '~3GB',
    speed: 'Fast'
  },
  {
    id: 'Phi-3.5-mini-instruct-q4f16_1-MLC',
    name: 'Phi 3.5 Mini',
    size: '3.8B',
    description: 'Microsoft\'s compact model',
    ram: '~4GB',
    speed: 'Medium'
  },
  {
    id: 'Qwen2-1.5B-Instruct-q4f16_1-MLC',
    name: 'Qwen2 1.5B',
    size: '1.5B',
    description: 'Alibaba\'s lightweight model',
    ram: '~2GB',
    speed: 'Very Fast'
  },
];

const PROMPT_TEMPLATES = [
  { id: 'default', name: 'Default Assistant', prompt: 'You are a helpful AI assistant.' },
  { id: 'coder', name: 'Code Expert', prompt: 'You are an expert programmer. Help with coding questions, debugging, and best practices. Provide clear code examples.' },
  { id: 'writer', name: 'Creative Writer', prompt: 'You are a creative writer. Help with writing stories, articles, and creative content. Be imaginative and engaging.' },
  { id: 'analyst', name: 'Data Analyst', prompt: 'You are a data analyst. Help analyze data, explain statistics, and provide insights. Be precise and analytical.' },
];

const QUICK_PROMPTS = [
  { title: 'Explain a concept', description: 'Get clear explanations of complex topics', text: 'Explain [topic] like I\'m 5 years old' },
  { title: 'Write code', description: 'Generate code snippets in any language', text: 'Write a [language] function that [does what]' },
  { title: 'Brainstorm ideas', description: 'Get creative ideas for your projects', text: 'Give me 10 ideas for [topic]' },
  { title: 'Summarize text', description: 'Create concise summaries', text: 'Summarize this text: [paste text]' },
];

interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
  timestamp?: number;
}

interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  modelId: string;
  settings: ChatSettings;
  createdAt: number;
  updatedAt: number;
}

interface ChatSettings {
  temperature: number;
  maxTokens: number;
  systemPrompt: string;
  streamResponses: boolean;
  autoSave: boolean;
}

const DEFAULT_SETTINGS: ChatSettings = {
  temperature: 0.7,
  maxTokens: 2048,
  systemPrompt: 'You are a helpful AI assistant.',
  streamResponses: true,
  autoSave: true,
};

const STORAGE_KEY = 'webllm-conversations';

export default function WebLLMChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isModelLoading, setIsModelLoading] = useState(false);
  const [progress, setProgress] = useState('');
  const [progressVal, setProgressVal] = useState(0);
  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [settings, setSettings] = useState<ChatSettings>(DEFAULT_SETTINGS);
  const [copiedMessageIndex, setCopiedMessageIndex] = useState<number | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [showQuickPrompts, setShowQuickPrompts] = useState(true);

  const engine = useRef<MLCEngine | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

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
  }, []);

  useEffect(() => {
    if (conversations.length > 0 && settings.autoSave) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    }
  }, [conversations, settings.autoSave]);

  useEffect(() => {
    if (activeConversationId) {
      const conv = conversations.find(c => c.id === activeConversationId);
      if (conv) {
        setMessages(conv.messages);
        setSettings(conv.settings);
        setShowQuickPrompts(false);
      }
    }
  }, [activeConversationId, conversations]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const updateActiveConversation = useCallback((newMessages: Message[]) => {
    if (!activeConversationId) return;

    setConversations(prev =>
      prev.map(conv =>
        conv.id === activeConversationId
          ? { ...conv, messages: newMessages, updatedAt: Date.now() }
          : conv
      )
    );
  }, [activeConversationId]);

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

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isLoading || isModelLoading || !selectedModel) return;

    if (!engine.current) {
      console.error("Engine not initialized. Please load a model first.");
      return;
    }

    // Track chat message
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

    const userMessage: Message = { role: 'user', content: input.trim(), timestamp: Date.now() };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);
    setShowQuickPrompts(false);

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
    }

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
        setMessages([...newMessages, { role: 'assistant' as const, content: assistantMessage, timestamp: Date.now() }]);
      }

      const finalMessages = [...newMessages, { role: 'assistant' as const, content: assistantMessage, timestamp: Date.now() }];
      updateActiveConversation(finalMessages);

      // Track assistant response
      try {
        const analytics = getAnalytics();
        analytics.trackChatMessage('assistant', 'llm', assistantMessage.length);
        analytics.trackFeatureUsage('llm_chat', 'message_received', {
          model: selectedModel,
          responseLength: assistantMessage.length,
          responseTime: Date.now() - userMessage.timestamp
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

  const handleModelChange = async (modelId: string) => {
    setSelectedModel(modelId);

    // Track model change
    try {
      const analytics = getAnalytics();
      analytics.trackFeatureUsage('llm_chat', 'model_changed', {
        fromModel: selectedModel,
        toModel: modelId
      });
    } catch (error) {
      // Analytics not initialized, silently ignore
    }

    await loadModel(modelId);
  };

  const createNewConversation = () => {
    setActiveConversationId(null);
    setMessages([]);
    setShowQuickPrompts(true);
    inputRef.current?.focus();
  };

  const deleteConversation = (id: string) => {
    setConversations(prev => prev.filter(c => c.id !== id));
    if (activeConversationId === id) {
      setActiveConversationId(null);
      setMessages([]);
      setShowQuickPrompts(true);
    }
  };

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
        setMessages([...messagesWithoutLast, { role: 'assistant' as const, content: assistantMessage, timestamp: Date.now() }]);
      }

      const finalMessages = [...messagesWithoutLast, { role: 'assistant' as const, content: assistantMessage, timestamp: Date.now() }];
      updateActiveConversation(finalMessages);
    } catch (err) {
      console.error('Failed to regenerate response:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const formatTimestamp = (timestamp?: number) => {
    if (!timestamp) return '';
    return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const activeConversation = conversations.find(c => c.id === activeConversationId);

  return (
    <SimpleLayout showHeader={true}>
      <div className="flex flex-col h-[calc(100vh-4rem)] bg-background">
        {/* Enhanced Toolbar */}
        <div className="flex items-center justify-between px-6 py-3 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shrink-0">
          <div className="flex items-center gap-3">
            {/* Conversation Dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="gap-2">
                  <MessageSquare className="w-4 h-4" />
                  <span className="max-w-[150px] truncate hidden sm:inline">
                    {activeConversation?.title || 'New Conversation'}
                  </span>
                  <ChevronDown className="w-3 h-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-72">
                <DropdownMenuLabel className="flex items-center gap-2">
                  <MessageSquare className="w-4 h-4" />
                  Conversations
                  {conversations.length > 0 && (
                    <Badge variant="secondary" className="ml-auto">
                      {conversations.length}
                    </Badge>
                  )}
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={createNewConversation}>
                  <Plus className="w-4 h-4 mr-2" />
                  New Conversation
                  <kbd className="ml-auto text-xs bg-muted px-1.5 py-0.5 rounded">⌘N</kbd>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                {conversations.length === 0 ? (
                  <div className="px-2 py-4 text-sm text-muted-foreground text-center">
                    No conversations yet
                  </div>
                ) : (
                  <ScrollArea className="max-h-64">
                    {conversations.map(conv => (
                      <DropdownMenuItem
                        key={conv.id}
                        onClick={() => setActiveConversationId(conv.id)}
                        className="flex items-center justify-between gap-2 p-3"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="truncate text-sm font-medium">{conv.title}</p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {conv.messages.length} messages • {formatTimestamp(conv.updatedAt)}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteConversation(conv.id);
                          }}
                        >
                          <Trash2 className="w-3 h-3" />
                        </Button>
                      </DropdownMenuItem>
                    ))}
                  </ScrollArea>
                )}
              </DropdownMenuContent>
            </DropdownMenu>

            {/* Enhanced Model Selector */}
            <HoverCard>
              <HoverCardTrigger asChild>
                <Button variant="outline" size="sm" className="gap-2" disabled={isModelLoading}>
                  <Cpu className="w-4 h-4" />
                  <span className="max-w-[120px] truncate hidden sm:inline">
                    {isModelLoading ? 'Loading...' : selectedModel ? AVAILABLE_MODELS.find(m => m.id === selectedModel)?.name : 'Select Model'}
                  </span>
                  {selectedModel && (
                    <Badge variant="secondary" className="text-xs">
                      {AVAILABLE_MODELS.find(m => m.id === selectedModel)?.size}
                    </Badge>
                  )}
                  <ChevronDown className="w-3 h-3" />
                </Button>
              </HoverCardTrigger>
              {selectedModel && (
                <HoverCardContent className="w-80" align="start">
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium">
                      {AVAILABLE_MODELS.find(m => m.id === selectedModel)?.name}
                    </h4>
                    <p className="text-xs text-muted-foreground">
                      {AVAILABLE_MODELS.find(m => m.id === selectedModel)?.description}
                    </p>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Zap className="w-3 h-3" />
                        {AVAILABLE_MODELS.find(m => m.id === selectedModel)?.speed}
                      </span>
                      <span className="flex items-center gap-1">
                        <Cpu className="w-3 h-3" />
                        {AVAILABLE_MODELS.find(m => m.id === selectedModel)?.ram}
                      </span>
                    </div>
                  </div>
                </HoverCardContent>
              )}
            </HoverCard>

            {selectedModel && (
              <Badge variant="outline" className="text-xs">
                <div className="w-2 h-2 bg-green-500 rounded-full mr-1.5" />
                Ready
              </Badge>
            )}
          </div>

          <div className="flex items-center gap-1">
            {/* Prompt Templates */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm">
                  <Sparkles className="w-4 h-4" />
                  <span className="hidden sm:inline ml-1">Prompts</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>System Prompts</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {PROMPT_TEMPLATES.map(template => (
                  <DropdownMenuItem
                    key={template.id}
                    onClick={() => setSettings({ ...settings, systemPrompt: template.prompt })}
                    className="flex flex-col items-start p-3"
                  >
                    <span className="font-medium">{template.name}</span>
                    <span className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                      {template.prompt}
                    </span>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

            {/* Enhanced Settings Dialog */}
            <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
              <DialogTrigger asChild>
                <Button variant="ghost" size="sm">
                  <Settings className="w-4 h-4" />
                  <span className="hidden sm:inline ml-1">Settings</span>
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <Settings className="w-5 h-5" />
                    Model Settings
                  </DialogTitle>
                </DialogHeader>
                <Tabs defaultValue="model" className="w-full">
                  <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="model">Model</TabsTrigger>
                    <TabsTrigger value="advanced">Advanced</TabsTrigger>
                    <TabsTrigger value="chat">Chat</TabsTrigger>
                  </TabsList>

                  <TabsContent value="model" className="space-y-6 mt-6">
                    <div>
                      <Label>Temperature: {settings.temperature}</Label>
                      <p className="text-xs text-muted-foreground mb-3">
                        Controls randomness. Lower values make responses more focused.
                      </p>
                      <Slider
                        value={[settings.temperature]}
                        onValueChange={([value]) => setSettings({ ...settings, temperature: value })}
                        min={0}
                        max={2}
                        step={0.1}
                        className="mt-2"
                      />
                    </div>
                    <div>
                      <Label>Max Tokens: {settings.maxTokens}</Label>
                      <p className="text-xs text-muted-foreground mb-3">
                        Maximum number of tokens in the response.
                      </p>
                      <Slider
                        value={[settings.maxTokens]}
                        onValueChange={([value]) => setSettings({ ...settings, maxTokens: value })}
                        min={128}
                        max={4096}
                        step={128}
                        className="mt-2"
                      />
                    </div>
                    <div>
                      <Label>System Prompt</Label>
                      <Textarea
                        value={settings.systemPrompt}
                        onChange={(e) => setSettings({ ...settings, systemPrompt: e.target.value })}
                        className="mt-2 min-h-[100px]"
                        placeholder="Enter system prompt..."
                      />
                    </div>
                  </TabsContent>

                  <TabsContent value="advanced" className="space-y-6 mt-6">
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label>Stream responses</Label>
                          <p className="text-xs text-muted-foreground">
                            See responses as they're being generated
                          </p>
                        </div>
                        <Switch
                          checked={settings.streamResponses}
                          onCheckedChange={(checked) => setSettings({ ...settings, streamResponses: checked })}
                        />
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label>Auto-save conversations</Label>
                          <p className="text-xs text-muted-foreground">
                            Automatically save chat history
                          </p>
                        </div>
                        <Switch
                          checked={settings.autoSave}
                          onCheckedChange={(checked) => setSettings({ ...settings, autoSave: checked })}
                        />
                      </div>
                    </div>
                  </TabsContent>

                  <TabsContent value="chat" className="space-y-6 mt-6">
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-sm">
                        <Clock className="w-4 h-4" />
                        <span className="font-medium">Keyboard shortcuts</span>
                      </div>
                      <div className="grid grid-cols-2 gap-3 text-xs">
                        <div className="flex justify-between p-2 bg-muted rounded">
                          <span>New chat</span>
                          <kbd className="bg-background px-1.5 py-0.5 rounded">⌘N</kbd>
                        </div>
                        <div className="flex justify-between p-2 bg-muted rounded">
                          <span>Send message</span>
                          <kbd className="bg-background px-1.5 py-0.5 rounded">Enter</kbd>
                        </div>
                        <div className="flex justify-between p-2 bg-muted rounded">
                          <span>New line</span>
                          <kbd className="bg-background px-1.5 py-0.5 rounded">Shift+Enter</kbd>
                        </div>
                        <div className="flex justify-between p-2 bg-muted rounded">
                          <span>Regenerate</span>
                          <kbd className="bg-background px-1.5 py-0.5 rounded">⌘R</kbd>
                        </div>
                      </div>
                    </div>
                  </TabsContent>
                </Tabs>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Enhanced Model Loading Progress */}
        {isModelLoading && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="px-6 py-3 bg-gradient-to-r from-blue-500/5 to-purple-500/5 border-b"
          >
            <div className="flex items-center gap-4 max-w-2xl mx-auto">
              <div className="relative">
                <Loader2 className="w-5 h-5 text-primary animate-spin" />
                <div className="absolute -inset-2 bg-primary/10 rounded-full animate-ping" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">Loading model...</p>
                <p className="text-xs text-muted-foreground truncate">{progress}</p>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-sm font-medium text-primary">
                  {Math.round(progressVal * 100)}%
                </div>
                <div className="w-32 h-2 bg-muted rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-primary to-primary/80"
                    initial={{ width: 0 }}
                    animate={{ width: `${progressVal * 100}%` }}
                    transition={{ duration: 0.3 }}
                  />
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Messages Area */}
        <div className="flex-1 overflow-auto min-h-0">
          <div className="max-w-3xl mx-auto px-6 py-8">
            {/* Enhanced Empty State */}
            {messages.length === 0 && !selectedModel && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col items-center justify-center py-20 text-center"
              >
                <div className="relative">
                  <div className="absolute inset-0 bg-gradient-to-r from-primary/20 to-purple-500/20 rounded-full blur-3xl" />
                  <div className="relative w-32 h-32 bg-gradient-to-br from-primary/10 to-primary/5 rounded-full flex items-center justify-center border border-primary/20">
                    <Bot className="w-16 h-16 text-primary" />
                  </div>
                </div>
                <h2 className="mt-8 text-3xl font-bold tracking-tight">Welcome to WebLLM Chat</h2>
                <p className="mt-3 text-lg text-muted-foreground max-w-lg">
                  Run AI models directly in your browser with complete privacy
                    </p>
                <div className="mt-8">
                  <div className="flex flex-wrap gap-3 justify-center">
                    {AVAILABLE_MODELS.slice(0, 3).map(model => (
                      <Button
                        key={model.id}
                        variant="outline"
                        size="lg"
                        onClick={() => handleModelChange(model.id)}
                        className="gap-2 h-12 px-6 group"
                      >
                        <Cpu className="w-4 h-4 group-hover:rotate-12 transition-transform" />
                        <span>{model.name}</span>
                        <Badge variant="secondary" className="text-xs">{model.size}</Badge>
                      </Button>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground mt-4">
                    WebGPU required • Models run locally in your browser
                  </p>
                </div>
              </motion.div>
            )}

            {/* Enhanced Ready State */}
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
                    {AVAILABLE_MODELS.find(m => m.id === selectedModel)?.name}
                  </span>
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  Type a message below to start the conversation
                </p>
              </motion.div>
            )}

            {/* Enhanced Messages with Quick Prompts */}
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
                    <Button
                      key={idx}
                      variant="outline"
                      className="h-auto p-4 text-left justify-start"
                      onClick={() => setInput(prompt.text)}
                    >
                      <div>
                        <p className="font-medium">{prompt.title}</p>
                        <p className="text-sm text-muted-foreground mt-0.5">
                          {prompt.description}
                        </p>
                      </div>
                    </Button>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Messages */}
            <AnimatePresence mode="wait">
              {messages.map((message, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className={cn(
                    "group relative mb-6",
                    message.role === 'user' && "ml-auto max-w-[80%]"
                  )}
                >
                  <div className="flex gap-3">
                    <Avatar className="w-8 h-8 shrink-0">
                      <AvatarFallback className={cn(
                        "text-xs font-medium",
                        message.role === 'user'
                          ? "bg-muted"
                          : "bg-primary/10 text-primary"
                      )}>
                        {message.role === 'user' ? (
                          <User className="w-4 h-4" />
                        ) : (
                          <Bot className="w-4 h-4" />
                        )}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1 space-y-2 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium opacity-70">
                          {message.role === 'user' ? 'You' : 'Assistant'}
                        </span>
                        {message.timestamp && (
                          <span className="text-xs opacity-50">
                            {formatTimestamp(message.timestamp)}
                          </span>
                        )}
                      </div>
                      <div className={cn(
                        "rounded-xl px-4 py-3 shadow-sm",
                        message.role === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted/50'
                      )}>
                        <p className="text-sm whitespace-pre-wrap break-words leading-relaxed">
                          {message.content}
                        </p>
                      </div>
                      {message.role === 'assistant' && (
                        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-xs text-muted-foreground"
                            onClick={() => copyMessage(message.content, idx)}
                          >
                            {copiedMessageIndex === idx ? (
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
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-xs text-muted-foreground"
                            onClick={regenerateResponse}
                            disabled={isLoading}
                          >
                            <RefreshCw className="w-3 h-3 mr-1" />
                            Regenerate
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {/* Enhanced Loading Indicator */}
            {isLoading && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex gap-3 mb-6"
              >
                <Avatar className="w-8 h-8">
                  <AvatarFallback className="bg-primary/10 text-primary">
                    <Bot className="w-4 h-4" />
                  </AvatarFallback>
                </Avatar>
                <div className="bg-muted/50 rounded-xl px-4 py-3 shadow-sm">
                  <div className="flex gap-1 items-center">
                    <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
                    <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-delay:0.2s]" />
                    <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-delay:0.4s]" />
                    <span className="text-xs text-muted-foreground ml-2">Assistant is typing</span>
                  </div>
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Enhanced Input Area */}
        <div className="border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 p-4 shrink-0">
          <div className="max-w-3xl mx-auto">
            <div className="relative group">
              <Textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={selectedModel ? "Type your message... (Enter to send, Shift+Enter for new line)" : "Select a model first..."}
                className="min-h-[60px] max-h-[200px] pr-20 resize-none border-2 shadow-sm focus:shadow-md transition-shadow"
                rows={1}
                disabled={!selectedModel || isLoading || isModelLoading}
              />
              <div className="absolute bottom-3 right-3 flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                  disabled={!selectedModel || isLoading}
                >
                  <Plus className="w-4 h-4" />
                </Button>
                <Button
                  onClick={() => handleSubmit()}
                  disabled={!input.trim() || !selectedModel || isLoading}
                  size="icon"
                  className="h-8 w-8"
                >
                  {isLoading ? (
                    <Square className="w-4 h-4" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </Button>
              </div>
            </div>
            {selectedModel && (
              <p className="text-xs text-muted-foreground mt-2 text-center">
                Powered by {AVAILABLE_MODELS.find(m => m.id === selectedModel)?.name} • Responses are generated locally
              </p>
            )}
          </div>
        </div>
      </div>
    </SimpleLayout>
  );
}