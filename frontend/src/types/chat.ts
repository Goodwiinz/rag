export interface Assistant {
  id: string
  name: string
  description: string
  avatar?: string
  category: string
  capabilities: string[]
  color: string
  // Optional metadata
  model?: string
  version?: string
  tags?: string[]
  isPremium?: boolean
  isActive?: boolean
  // Statistics
  usageCount?: number
  avgRating?: number
  lastUsed?: Date
}

export interface AssistantCategory {
  id: string
  name: string
  description: string
  icon: string
  color: string
}

export interface ChatSession {
  id: string
  assistantId: string
  title: string
  messages: ChatMessage[]
  createdAt: Date
  updatedAt: Date
  metadata?: {
    model?: string
    tokens?: number
    cost?: number
  }
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  metadata?: {
    model?: string
    tokens?: number
    thinking?: string
    sources?: string[]
  }
}

export interface ChatPreferences {
  defaultAssistant?: string
  autoSave: boolean
  showTimestamps: boolean
  showThinking: boolean
  theme: 'light' | 'dark' | 'system'
  fontSize: 'small' | 'medium' | 'large'
}

export interface ChatAnalytics {
  totalSessions: number
  totalMessages: number
  totalTokens: number
  averageSessionLength: number
  mostUsedAssistant: string
  assistantUsage: Record<string, number>
  dailyUsage: Record<string, number>
}

// Pre-defined assistant categories
export const ASSISTANT_CATEGORIES: AssistantCategory[] = [
  {
    id: 'general',
    name: 'General',
    description: 'General purpose assistants for everyday tasks',
    icon: 'sparkles',
    color: 'blue'
  },
  {
    id: 'development',
    name: 'Development',
    description: 'Programming and technical assistance',
    icon: 'code',
    color: 'purple'
  },
  {
    id: 'creative',
    name: 'Creative',
    description: 'Writing, art, and creative tasks',
    icon: 'pen-tool',
    color: 'green'
  },
  {
    id: 'business',
    name: 'Business',
    description: 'Business analysis and strategy',
    icon: 'briefcase',
    color: 'orange'
  },
  {
    id: 'academic',
    name: 'Academic',
    description: 'Research and academic support',
    icon: 'graduation-cap',
    color: 'indigo'
  },
  {
    id: 'health',
    name: 'Health',
    description: 'Health and wellness guidance',
    icon: 'heart',
    color: 'red'
  }
]

// Assistant capability tags
export const ASSISTANT_CAPABILITIES = [
  'Code generation',
  'Debugging',
  'Code review',
  'Documentation',
  'Content creation',
  'Editing',
  'Proofreading',
  'Style suggestions',
  'Market analysis',
  'Strategic planning',
  'Data insights',
  'Reports',
  'General knowledge',
  'Text processing',
  'Basic analysis',
  'Literature review',
  'Data analysis',
  'Citation management',
  'Methodology',
  'UI design',
  'UX research',
  'Prototyping',
  'Design systems',
  'Translation',
  'Language learning',
  'Math problem solving',
  'Scientific computing'
]