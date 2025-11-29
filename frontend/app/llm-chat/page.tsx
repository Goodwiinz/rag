'use client';

import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useWebLLM } from '@/hooks/useWebLLM';
import { 
  Bot, 
  Loader2, 
  Send, 
  Settings, 
  MessageSquare, 
  Plus, 
  Globe, 
  Github,
  Pencil,
  Share2,
  RotateCcw,
  Maximize2,
  Sparkles,
  Image as ImageIcon,
  GripVertical,
  User,
  Cpu,
} from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';

const AVAILABLE_MODELS = [
  { id: 'Llama-3.2-1B-Instruct-q4f32_1-MLC', name: 'Llama 3.2 1B' },
  { id: 'Llama-3.2-3B-Instruct-q4f32_1-MLC', name: 'Llama 3.2 3B' },
  { id: 'gemma-2-2b-it-q4f16_1-MLC', name: 'Gemma 2 2B' },
  { id: 'Phi-3.5-mini-instruct-q4f16_1-MLC', name: 'Phi 3.5 Mini' },
  { id: 'Qwen2-1.5B-Instruct-q4f16_1-MLC', name: 'Qwen2 1.5B' },
];

export default function WebLLMChatPage() {
  const {
    messages,
    isLoading,
    isModelLoading,
    progressVal,
    progress,
    sendMessage,
    loadModel,
    resetChat,
    error,
  } = useWebLLM();

  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (!isModelLoading && selectedModel && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isModelLoading, selectedModel]);

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isLoading || isModelLoading || !selectedModel) return;
    const message = input;
    setInput('');
    await sendMessage(message);
  };

  const handleModelChange = async (modelId: string) => {
    setSelectedModel(modelId);
    await loadModel(modelId);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const formatDate = (date: Date) => {
    return date.toLocaleString('en-US', { 
      month: 'numeric', 
      day: 'numeric', 
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      second: '2-digit',
      hour12: true 
    });
  };

  return (
    <div className="h-[calc(100vh-120px)] w-full flex rounded-xl overflow-hidden bg-background border border-border shadow-sm">
      {/* Sidebar */}
      <div className="w-[280px] flex flex-col bg-muted/30 border-r border-border shrink-0 relative">
        {/* Sidebar Header */}
        <div className="p-4 flex items-start justify-between">
          <div>
            <h1 className="text-sm font-semibold text-foreground">WebLLM Chat</h1>
            <p className="text-xs text-muted-foreground mt-0.5">AI in Your Browser</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
            <Bot className="w-5 h-5 text-amber-600" />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="px-3 pb-3 grid grid-cols-2 gap-2">
          <button className="h-8 px-3 rounded-md bg-background border border-border text-xs font-medium text-foreground flex items-center justify-center gap-1.5 hover:bg-muted transition-colors">
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            Prompts
          </button>
          <button className="h-8 px-3 rounded-md bg-background border border-border text-xs font-medium text-foreground flex items-center justify-center gap-1.5 hover:bg-muted transition-colors">
            <Settings className="w-3.5 h-3.5 text-muted-foreground" />
            Settings
          </button>
        </div>

        {/* Conversations Label */}
        <div className="px-4 py-2">
          <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Conversations</span>
        </div>

        {/* Chat List */}
        <div className="flex-1 overflow-y-auto px-3">
          <div className="bg-background rounded-lg p-3 border border-border cursor-pointer hover:border-amber-500/50 transition-colors">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-muted-foreground" />
              <span className="font-medium text-sm text-foreground">New Conversation</span>
            </div>
            <div className="flex justify-between items-center mt-2 text-xs text-muted-foreground">
              <span>{messages.length} messages</span>
              <span>{formatDate(new Date())}</span>
            </div>
          </div>
        </div>

        {/* Sidebar Footer */}
        <div className="p-3 border-t border-border">
          <div className="flex items-center gap-1 mb-3">
            <Link 
              href="https://webllm.mlc.ai" 
              target="_blank"
              className="w-8 h-8 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <Globe className="w-4 h-4" />
            </Link>
            <Link 
              href="https://github.com/mlc-ai/web-llm" 
              target="_blank"
              className="w-8 h-8 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <Github className="w-4 h-4" />
            </Link>
            <div className="flex-1" />
            <span className="text-[10px] text-muted-foreground">v1.0</span>
          </div>
          <button 
            onClick={resetChat}
            disabled={isModelLoading}
            className="w-full h-9 rounded-md bg-amber-500 hover:bg-amber-600 text-white text-xs font-medium flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col bg-background min-w-0">
        {/* Chat Header */}
        <div className="h-14 px-5 border-b border-border flex items-center justify-between shrink-0">
          <div>
            <h2 className="text-sm font-semibold text-foreground">New Conversation</h2>
            <p className="text-xs text-muted-foreground">{messages.length === 0 ? 'No messages yet' : `${messages.length} messages`}</p>
          </div>
          <div className="flex items-center gap-1">
            <button className="w-8 h-8 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
              <Pencil className="w-4 h-4" />
            </button>
            <button className="w-8 h-8 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
              <Share2 className="w-4 h-4" />
            </button>
            <button 
              onClick={resetChat}
              className="w-8 h-8 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
            <button className="w-8 h-8 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
              <Maximize2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="h-full flex items-center justify-center p-8">
              <div className="text-center max-w-md">
                {!selectedModel ? (
                  <>
                    <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-amber-500/10 flex items-center justify-center">
                      <Cpu className="w-8 h-8 text-amber-500" />
                    </div>
                    <h3 className="text-base font-semibold text-foreground mb-2">Select a Model</h3>
                    <p className="text-sm text-muted-foreground mb-6">
                      Choose an AI model from the toolbar below to start chatting.<br />
                      Models run entirely in your browser.
                    </p>
                    <div className="flex flex-wrap justify-center gap-2">
                      {AVAILABLE_MODELS.slice(0, 3).map((model) => (
                        <button
                          key={model.id}
                          onClick={() => handleModelChange(model.id)}
                          className="h-8 px-4 rounded-md border border-border bg-background text-xs font-medium text-foreground hover:border-amber-500 hover:text-amber-600 transition-colors"
                        >
                          {model.name}
                        </button>
                      ))}
                    </div>
                  </>
                ) : isModelLoading ? (
                  <>
                    <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-amber-500/10 flex items-center justify-center">
                      <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
                    </div>
                    <h3 className="text-base font-semibold text-foreground mb-2">Loading Model</h3>
                    <p className="text-sm text-muted-foreground mb-4">{progress || 'Initializing...'}</p>
                    <div className="w-64 mx-auto h-2 bg-muted rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-amber-500 transition-all duration-300 rounded-full"
                        style={{ width: `${Math.round(progressVal * 100)}%` }}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">{Math.round(progressVal * 100)}% complete</p>
                  </>
                ) : (
                  <>
                    <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-green-500/10 flex items-center justify-center">
                      <MessageSquare className="w-8 h-8 text-green-500" />
                    </div>
                    <h3 className="text-base font-semibold text-foreground mb-2">Ready to Chat</h3>
                    <p className="text-sm text-muted-foreground">
                      Model loaded successfully. Type a message below to start.
                    </p>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="p-6 space-y-6 max-w-3xl mx-auto">
              {messages.map((message, i) => (
                <div key={i} className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}>
                  <div className={`w-8 h-8 rounded-full shrink-0 flex items-center justify-center ${
                    message.role === 'user' 
                      ? 'bg-amber-500' 
                      : 'bg-muted'
                  }`}>
                    {message.role === 'user' ? (
                      <User className="w-4 h-4 text-white" />
                    ) : (
                      <Bot className="w-4 h-4 text-foreground" />
                    )}
                  </div>
                  <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    message.role === 'user'
                      ? 'bg-amber-500 text-white'
                      : 'bg-muted text-foreground'
                  }`}>
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  </div>
                </div>
              ))}
              
              {isLoading && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full shrink-0 flex items-center justify-center bg-muted">
                    <Bot className="w-4 h-4 text-foreground" />
                  </div>
                  <div className="bg-muted rounded-2xl px-4 py-3">
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                      <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                      <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                    </div>
                  </div>
                </div>
              )}
              
              {error && (
                <div className="bg-destructive/10 text-destructive text-sm rounded-xl px-4 py-3 border border-destructive/20">
                  Error: {error}
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-border p-4 shrink-0">
          {/* Action Toolbar */}
          <div className="flex items-center gap-2 mb-3">
            <div className="flex items-center gap-1 p-1 rounded-lg border border-border bg-muted/50">
              <button className="w-7 h-7 rounded flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-background transition-colors">
                <Pencil className="w-3.5 h-3.5" />
              </button>
              <button className="w-7 h-7 rounded flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-background transition-colors">
                <Sparkles className="w-3.5 h-3.5" />
              </button>
              <button className="w-7 h-7 rounded flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-background transition-colors">
                <ImageIcon className="w-3.5 h-3.5" />
              </button>
            </div>
            
            <div className="flex-1" />
            
            {isModelLoading && (
              <div className="flex items-center gap-2 px-2.5 py-1 bg-amber-500/10 rounded-md text-xs text-amber-600">
                <Loader2 className="w-3 h-3 animate-spin" />
                {Math.round(progressVal * 100)}%
              </div>
            )}
            
            <Select value={selectedModel} onValueChange={handleModelChange} disabled={isModelLoading}>
              <SelectTrigger className="h-8 w-auto min-w-[200px] text-xs bg-muted/50 border-border">
                <Bot className="w-4 h-4 mr-2 text-amber-500" />
                <SelectValue placeholder="Select a model..." />
              </SelectTrigger>
              <SelectContent>
                {AVAILABLE_MODELS.map((model) => (
                  <SelectItem key={model.id} value={model.id} className="text-xs">
                    {model.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Text Input */}
          <div className="relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={selectedModel ? "Type your message... (Enter to send, Shift+Enter for new line)" : "Select a model to start chatting..."}
              disabled={!selectedModel || isModelLoading || isLoading}
              className="w-full resize-none rounded-xl border border-border bg-background pl-4 pr-24 py-3.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 disabled:opacity-50 disabled:cursor-not-allowed min-h-[56px] transition-colors"
              rows={1}
            />
            <button
              onClick={() => handleSubmit()}
              disabled={!selectedModel || isModelLoading || isLoading || !input.trim()}
              className="absolute right-3 bottom-3 h-9 px-4 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
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
