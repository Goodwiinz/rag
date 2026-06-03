'use client';

import * as React from 'react';
import { useState } from 'react';
import { MessageSquarePlus } from 'lucide-react';
import { NewChatDialog, Assistant } from '@/components/ui/new-chat-dialog';
import { Button } from '@/components/ui/button';

export function NewChatDialogDemo() {
  const [isOpen, setIsOpen] = useState(false);
  const [chatHistory, setChatHistory] = useState<
    { assistant: Assistant; timestamp: Date }[]
  >([]);

  // Extended list of assistants for demo
  const [assistants] = useState<Assistant[]>([
    {
      id: 'default',
      name: 'Default',
      description: 'General purpose assistant for everyday tasks and questions',
      avatar: '',
      category: 'general',
      capabilities: ['General knowledge', 'Text processing', 'Basic analysis'],
      color: 'from-blue-500 to-cyan-500',
    },
    {
      id: 'code',
      name: 'Code Assistant',
      description: 'Specialized in programming, debugging, and code review',
      avatar: '',
      category: 'development',
      capabilities: [
        'Code generation',
        'Debugging',
        'Code review',
        'Documentation',
      ],
      color: 'from-[var(--nous-sol)] to-[var(--nous-helios)]',
    },
    {
      id: 'writing',
      name: 'Writing Assistant',
      description: 'Help with writing, editing, and content creation',
      avatar: '',
      category: 'creative',
      capabilities: [
        'Content creation',
        'Editing',
        'Proofreading',
        'Style suggestions',
      ],
      color: 'from-green-500 to-emerald-500',
    },
    {
      id: 'business',
      name: 'Business Analyst',
      description: 'Business insights, analysis, and strategic planning',
      avatar: '',
      category: 'business',
      capabilities: [
        'Market analysis',
        'Strategic planning',
        'Data insights',
        'Reports',
      ],
      color: 'from-orange-500 to-red-500',
    },
    {
      id: 'research',
      name: 'Research Assistant',
      description: 'Academic research and detailed analysis support',
      avatar: '',
      category: 'academic',
      capabilities: [
        'Literature review',
        'Data analysis',
        'Citation management',
        'Methodology',
      ],
      color: 'from-[var(--nous-helios)] to-[var(--nous-sol)]',
    },
    {
      id: 'design',
      name: 'Design Assistant',
      description: 'UI/UX design guidance and creative direction',
      avatar: '',
      category: 'creative',
      capabilities: [
        'UI design',
        'UX research',
        'Prototyping',
        'Design systems',
      ],
      color: 'from-pink-500 to-rose-500',
    },
  ]);

  const handleSelectAssistant = (assistant: Assistant) => {
    setChatHistory((prev) => [
      { assistant, timestamp: new Date() },
      ...prev.slice(0, 4),
    ]);
    console.log(`Starting chat with ${assistant.name}`);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold text-foreground">
            AI Chat Assistant
          </h1>
          <p className="text-xl text-muted-foreground">
            Choose from our specialized AI assistants for your specific needs
          </p>
        </div>

        <div className="flex justify-center">
          <Button
            onClick={() => setIsOpen(true)}
            size="lg"
            className="h-14 px-8 bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white font-medium shadow-lg shadow-orange-500/25 transition-all duration-300"
          >
            <MessageSquarePlus className="h-5 w-5 mr-2" />
            Start New Chat
          </Button>
        </div>

        {chatHistory.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-2xl font-semibold">Recent Chats</h2>
            <div className="grid gap-3">
              {chatHistory.map((chat, index) => (
                <div
                  key={index}
                  className="p-4 rounded-lg bg-background/50 backdrop-blur-sm border border-border/50"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`h-10 w-10 rounded-full bg-gradient-to-br ${chat.assistant.color} flex items-center justify-center text-white font-semibold`}
                    >
                      {chat.assistant.name.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <p className="font-medium">{chat.assistant.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {chat.timestamp.toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <NewChatDialog
          open={isOpen}
          onOpenChange={setIsOpen}
          assistants={assistants}
          onSelectAssistant={handleSelectAssistant}
        />
      </div>
    </div>
  );
}
