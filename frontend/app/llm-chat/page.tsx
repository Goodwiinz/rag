'use client';

import { DashboardLayout } from '@/components/layout/dashboard/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Slider } from '@/components/ui/slider';
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
    User
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

const AVAILABLE_MODELS = [
  { id: 'Llama-3.2-1B-Instruct-q4f32_1-MLC', name: 'Llama 3.2 1B', size: '1B' },
  { id: 'Llama-3.2-3B-Instruct-q4f32_1-MLC', name: 'Llama 3.2 3B', size: '3B' },
  { id: 'gemma-2-2b-it-q4f16_1-MLC', name: 'Gemma 2 2B', size: '2B' },
  { id: 'Phi-3.5-mini-instruct-q4f16_1-MLC', name: 'Phi 3.5 Mini', size: '3.8B' },
  { id: 'Qwen2-1.5B-Instruct-q4f16_1-MLC', name: 'Qwen2 1.5B', size: '1.5B' },
];

const PROMPT_TEMPLATES = [
  { id: 'default', name: 'Default Assistant', prompt: 'You are a helpful AI assistant.' },
  { id: 'coder', name: 'Code Expert', prompt: 'You are an expert programmer. Help with coding questions, debugging, and best practices. Provide clear code examples.' },
  { id: 'writer', name: 'Creative Writer', prompt: 'You are a creative writer. Help with writing stories, articles, and creative content. Be imaginative and engaging.' },
  { id: 'analyst', name: 'Data Analyst', prompt: 'You are a data analyst. Help analyze data, explain statistics, and provide insights. Be precise and analytical.' },
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
}

const DEFAULT_SETTINGS: ChatSettings = {
  temperature: 0.7,
  maxTokens: 2048,
  systemPrompt: 'You are a helpful AI assistant.',
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
    if (conversations.length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    }
  }, [conversations]);

  useEffect(() => {
    if (activeConversationId) {
      const conv = conversations.find(c => c.id === activeConversationId);
      if (conv) {
        setMessages(conv.messages);
        setSettings(conv.settings);
      }
    }
  }, [activeConversationId, conversations]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const updateActiveConversation = (newMessages: Message[]) => {
    if (!activeConversationId) return;

    setConversations(prev =>
      prev.map(conv =>
        conv.id === activeConversationId
          ? { ...conv, messages: newMessages, updatedAt: Date.now() }
          : conv
      )
    );
  };

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

    const userMessage: Message = { role: 'user', content: input.trim(), timestamp: Date.now() };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);

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
        stream: true,
      });

      for await (const chunk of chunks) {
        const delta = chunk.choices[0]?.delta?.content || '';
        assistantMessage += delta;
        setMessages([...newMessages, { role: 'assistant' as const, content: assistantMessage, timestamp: Date.now() }]);
      }

      const finalMessages = [...newMessages, { role: 'assistant' as const, content: assistantMessage, timestamp: Date.now() }];
      updateActiveConversation(finalMessages);
    } catch (err) {
      console.error('Failed to send message:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleModelChange = async (modelId: string) => {
    setSelectedModel(modelId);
    await loadModel(modelId);
  };

  const createNewConversation = () => {
    setActiveConversationId(null);
    setMessages([]);
    inputRef.current?.focus();
  };

  const deleteConversation = (id: string) => {
    setConversations(prev => prev.filter(c => c.id !== id));
    if (activeConversationId === id) {
      setActiveConversationId(null);
      setMessages([]);
    }
  };

  const copyMessage = async (content: string, index: number) => {
    await navigator.clipboard.writeText(content);
    setCopiedMessageIndex(index);
    setTimeout(() => setCopiedMessageIndex(null), 2000);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const activeConversation = conversations.find(c => c.id === activeConversationId);

  return (
    <DashboardLayout fullHeight>
      <div className="flex flex-col h-full bg-background">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-4 py-2 border-b shrink-0">
          <div className="flex items-center gap-2">
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
              <DropdownMenuContent align="start" className="w-64">
                <DropdownMenuLabel>Conversations</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={createNewConversation}>
                  <Plus className="w-4 h-4 mr-2" />
                  New Conversation
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                {conversations.length === 0 ? (
                  <div className="px-2 py-3 text-sm text-muted-foreground text-center">
                    No conversations yet
                  </div>
                ) : (
                  <ScrollArea className="max-h-48">
                    {conversations.map(conv => (
                      <DropdownMenuItem
                        key={conv.id}
                        onClick={() => setActiveConversationId(conv.id)}
                        className="flex items-center justify-between gap-2"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="truncate text-sm">{conv.title}</p>
                          <p className="text-xs text-muted-foreground">{conv.messages.length} messages</p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 shrink-0"
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

            {/* Model Selector */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="gap-2" disabled={isModelLoading}>
                  <Bot className="w-4 h-4" />
                  <span className="max-w-[120px] truncate hidden sm:inline">
                    {isModelLoading ? 'Loading...' : selectedModel ? AVAILABLE_MODELS.find(m => m.id === selectedModel)?.name : 'Select Model'}
                  </span>
                  <ChevronDown className="w-3 h-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-52">
                <DropdownMenuLabel>Models</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {AVAILABLE_MODELS.map(model => (
                  <DropdownMenuItem
                    key={model.id}
                    onClick={() => handleModelChange(model.id)}
                    className="flex items-center justify-between"
                  >
                    <div>
                      <p className="text-sm">{model.name}</p>
                      <p className="text-xs text-muted-foreground">{model.size}</p>
                    </div>
                    {selectedModel === model.id && <Check className="w-4 h-4 text-primary" />}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
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
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuLabel>Templates</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {PROMPT_TEMPLATES.map(template => (
                  <DropdownMenuItem
                    key={template.id}
                    onClick={() => setSettings({ ...settings, systemPrompt: template.prompt })}
                  >
                    {template.name}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

            {/* Settings Dialog */}
            <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
              <DialogTrigger asChild>
                <Button variant="ghost" size="sm">
                  <Settings className="w-4 h-4" />
                  <span className="hidden sm:inline ml-1">Settings</span>
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Model Settings</DialogTitle>
                </DialogHeader>
                <div className="space-y-6 pt-4">
                  <div>
                    <Label>Temperature: {settings.temperature}</Label>
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
                    <textarea
                      value={settings.systemPrompt}
                      onChange={(e) => setSettings({ ...settings, systemPrompt: e.target.value })}
                      className="mt-2 w-full h-24 px-3 py-2 border rounded-md text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                      placeholder="Enter system prompt..."
                    />
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Model Loading Progress */}
        {isModelLoading && (
          <div className="px-4 py-2 bg-muted/50 border-b">
            <div className="flex items-center gap-3 max-w-2xl mx-auto">
              <Loader2 className="w-4 h-4 text-primary animate-spin" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">Loading model...</p>
                <p className="text-xs text-muted-foreground truncate">{progress}</p>
              </div>
              <div className="w-24 h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-300"
                  style={{ width: `${progressVal * 100}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Messages Area */}
        <div className="flex-1 overflow-auto min-h-0">
          <div className="max-w-2xl mx-auto px-4 py-6 space-y-4">
            {/* Empty State */}
            {messages.length === 0 && !selectedModel && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="w-14 h-14 bg-primary/10 rounded-full flex items-center justify-center mb-4">
                  <Bot className="w-7 h-7 text-primary" />
                </div>
                <h2 className="text-lg font-semibold mb-2">Welcome to WebLLM Chat</h2>
                <p className="text-muted-foreground text-sm mb-6 max-w-sm">
                  Run AI models directly in your browser. Select a model to get started.
                </p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {AVAILABLE_MODELS.slice(0, 3).map(model => (
                    <Button
                      key={model.id}
                      variant="outline"
                      size="sm"
                      onClick={() => handleModelChange(model.id)}
                      className="gap-2"
                    >
                      <Bot className="w-3 h-3" />
                      {model.name}
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {/* Ready State */}
            {messages.length === 0 && selectedModel && !isModelLoading && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="w-14 h-14 bg-green-500/10 rounded-full flex items-center justify-center mb-4">
                  <Check className="w-7 h-7 text-green-600" />
                </div>
                <h2 className="text-lg font-semibold mb-2">Model Ready</h2>
                <p className="text-muted-foreground text-sm">
                  Using <span className="font-medium text-foreground">{AVAILABLE_MODELS.find(m => m.id === selectedModel)?.name}</span>
                </p>
                <p className="text-xs text-muted-foreground mt-1">Type a message below to start</p>
              </div>
            )}

            {/* Messages */}
            <AnimatePresence>
              {messages.map((message, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex gap-3"
                >
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                    message.role === 'user' ? 'bg-muted' : 'bg-primary/10'
                  }`}>
                    {message.role === 'user' ? (
                      <User className="w-4 h-4" />
                    ) : (
                      <Bot className="w-4 h-4 text-primary" />
                    )}
                  </div>
                  <div className="flex-1 space-y-1 min-w-0">
                    <div className={`rounded-lg px-3 py-2 ${
                      message.role === 'user'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted'
                    }`}>
                      <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
                    </div>
                    {message.role === 'assistant' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs text-muted-foreground"
                        onClick={() => copyMessage(message.content, idx)}
                      >
                        {copiedMessageIndex === idx ? (
                          <><Check className="w-3 h-3 mr-1" /> Copied</>
                        ) : (
                          <><Copy className="w-3 h-3 mr-1" /> Copy</>
                        )}
                      </Button>
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {/* Loading Indicator */}
            {isLoading && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4 text-primary" />
                </div>
                <div className="bg-muted rounded-lg px-3 py-2">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce" />
                    <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce [animation-delay:0.2s]" />
                    <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce [animation-delay:0.4s]" />
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="border-t p-3 shrink-0">
          <div className="max-w-2xl mx-auto">
            <div className="relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={selectedModel ? "Type a message... (Enter to send)" : "Select a model first..."}
                className="w-full px-3 py-2 pr-12 bg-muted border-0 rounded-lg text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
                rows={1}
                disabled={!selectedModel || isLoading || isModelLoading}
              />
              <Button
                onClick={() => handleSubmit()}
                disabled={!input.trim() || !selectedModel || isLoading}
                size="icon"
                className="absolute right-1.5 bottom-1.5 h-7 w-7 rounded-md"
              >
                {isLoading ? <Square className="w-3 h-3" /> : <Send className="w-3 h-3" />}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
