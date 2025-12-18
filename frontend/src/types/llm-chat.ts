/**
 * Type definitions for LLM Chat feature
 */

export interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
  timestamp?: number;
  id?: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  modelId: string;
  settings: ChatSettings;
  createdAt: number;
  updatedAt: number;
}

export interface ChatSettings {
  temperature: number;
  maxTokens: number;
  systemPrompt: string;
}

export interface ModelInfo {
  id: string;
  name: string;
  size: string;
  description: string;
}

export interface PromptTemplate {
  id: string;
  name: string;
  icon: string;
  prompt: string;
}

export interface KeyboardShortcut {
  keys: string[];
  desc: string;
}
