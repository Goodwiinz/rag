'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import {
  Settings,
  Download,
  Upload,
  Moon,
  Sun,
  Save,
  RotateCcw,
  Trash2,
  Copy,
  Share,
  FileText,
  MessageSquare,
  Cpu,
  Zap,
  Shield,
  Bell,
  Globe,
  Palette,
  Sparkles,
  Code,
  BookOpen,
  Bot,
  User,
  Plus,
  X,
  CheckCircle2,
  AlertCircle,
  Info,
} from 'lucide-react';

export interface ChatSettings {
  // Model Settings
  temperature: number;
  maxTokens: number;
  topP: number;
  frequencyPenalty: number;
  presencePenalty: number;

  // System Prompt
  systemPrompt: string;
  systemPromptTemplate: string;

  // Chat Behavior
  streamResponses: boolean;
  autoSave: boolean;
  showTimestamps: boolean;
  showThinking: boolean;
  markdownRendering: boolean;

  // UI Settings
  theme: 'light' | 'dark' | 'system';
  fontSize: 'small' | 'medium' | 'large';
  compactMode: boolean;
  showAvatars: boolean;

  // Notifications
  soundEnabled: boolean;
  desktopNotifications: boolean;

  // Privacy & Security
  dataRetention: number; // days
  shareAnalytics: boolean;
}

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

const SYSTEM_PROMPT_TEMPLATES = [
  {
    id: 'default',
    name: 'Default Assistant',
    icon: <Bot className="w-4 h-4" />,
    prompt: 'You are a helpful AI assistant.',
    description: 'Balanced, helpful, and friendly',
  },
  {
    id: 'coder',
    name: 'Code Expert',
    icon: <Code className="w-4 h-4" />,
    prompt: 'You are an expert programmer. Provide clear, efficient code examples and explain complex programming concepts simply.',
    description: 'Specialized for coding and technical tasks',
  },
  {
    id: 'writer',
    name: 'Creative Writer',
    icon: <Sparkles className="w-4 h-4" />,
    prompt: 'You are a creative writer and storyteller. Help craft engaging content with vivid descriptions and compelling narratives.',
    description: 'Optimized for creative and narrative tasks',
  },
  {
    id: 'analyst',
    name: 'Data Analyst',
    icon: <FileText className="w-4 h-4" />,
    prompt: 'You are a data analyst. Provide precise, analytical insights with supporting evidence and clear explanations.',
    description: 'Focused on analysis and critical thinking',
  },
  {
    id: 'teacher',
    name: 'Educator',
    icon: <BookOpen className="w-4 h-4" />,
    prompt: 'You are an experienced teacher. Explain concepts clearly, provide examples, and use analogies to help others learn.',
    description: 'Patient and educational approach',
  },
];

interface ChatSettingsPanelProps {
  settings: ChatSettings;
  onSettingsChange: (settings: ChatSettings) => void;
  onReset?: () => void;
  onExport?: () => void;
  onImport?: (settings: ChatSettings) => void;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  className?: string;
}

export function ChatSettingsPanel({
  settings,
  onSettingsChange,
  onReset,
  onExport,
  onImport,
  isOpen,
  onOpenChange,
  className,
}: ChatSettingsPanelProps) {
  const [activeTab, setActiveTab] = useState('model');
  const [customPromptOpen, setCustomPromptOpen] = useState(false);
  const [customPromptName, setCustomPromptName] = useState('');
  const [customPromptContent, setCustomPromptContent] = useState('');
  const [savedPrompts, setSavedPrompts] = useState<any[]>([]);

  // Load saved prompts from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('custom-prompts');
    if (saved) {
      try {
        setSavedPrompts(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to load custom prompts:', e);
      }
    }
  }, []);

  const handleSettingChange = (key: keyof ChatSettings, value: any) => {
    onSettingsChange({ ...settings, [key]: value });
  };

  const handleReset = () => {
    onSettingsChange(DEFAULT_SETTINGS);
    onReset?.();
  };

  const handleExport = () => {
    const dataStr = JSON.stringify(settings, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'chat-settings.json';
    link.click();
    URL.revokeObjectURL(url);
    onExport?.();
  };

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const imported = JSON.parse(e.target?.result as string);
          onSettingsChange({ ...DEFAULT_SETTINGS, ...imported });
          onImport?.(imported);
        } catch (error) {
          console.error('Failed to import settings:', error);
        }
      };
      reader.readAsText(file);
    }
  };

  const saveCustomPrompt = () => {
    if (customPromptName && customPromptContent) {
      const newPrompt = {
        id: Date.now().toString(),
        name: customPromptName,
        prompt: customPromptContent,
        icon: <User className="w-4 h-4" />,
        custom: true,
      };
      const updated = [...savedPrompts, newPrompt];
      setSavedPrompts(updated);
      localStorage.setItem('custom-prompts', JSON.stringify(updated));
      setCustomPromptName('');
      setCustomPromptContent('');
      setCustomPromptOpen(false);
    }
  };

  const deleteCustomPrompt = (id: string) => {
    const updated = savedPrompts.filter(p => p.id !== id);
    setSavedPrompts(updated);
    localStorage.setItem('custom-prompts', JSON.stringify(updated));
  };

  const allPrompts = [...SYSTEM_PROMPT_TEMPLATES, ...savedPrompts];

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
            Chat Settings
          </DialogTitle>
          <DialogDescription>
            Customize your chat experience and model behavior
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-4">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="model" className="flex items-center gap-2">
                <Cpu className="w-4 h-4" />
                Model
              </TabsTrigger>
              <TabsTrigger value="behavior" className="flex items-center gap-2">
                <Bot className="w-4 h-4" />
                Behavior
              </TabsTrigger>
              <TabsTrigger value="appearance" className="flex items-center gap-2">
                <Palette className="w-4 h-4" />
                Appearance
              </TabsTrigger>
              <TabsTrigger value="privacy" className="flex items-center gap-2">
                <Shield className="w-4 h-4" />
                Privacy
              </TabsTrigger>
            </TabsList>

            <div className="mt-6">
              <TabsContent value="model" className="space-y-6">
                {/* Temperature */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Temperature</CardTitle>
                    <CardDescription>
                      Controls randomness. Lower values make responses more focused and deterministic.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Slider
                          value={[settings.temperature]}
                          onValueChange={([value]) => handleSettingChange('temperature', value)}
                          min={0}
                          max={2}
                          step={0.1}
                          className="flex-1 mr-4"
                        />
                        <Badge variant="outline" className="min-w-[50px] justify-center">
                          {settings.temperature}
                        </Badge>
                      </div>
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>Precise</span>
                        <span>Balanced</span>
                        <span>Creative</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Max Tokens */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Max Tokens</CardTitle>
                    <CardDescription>
                      Maximum number of tokens in the response. Higher values allow longer responses.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Slider
                          value={[settings.maxTokens]}
                          onValueChange={([value]) => handleSettingChange('maxTokens', value)}
                          min={128}
                          max={4096}
                          step={128}
                          className="flex-1 mr-4"
                        />
                        <Badge variant="outline" className="min-w-[60px] justify-center">
                          {settings.maxTokens}
                        </Badge>
                      </div>
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>128</span>
                        <span>2048</span>
                        <span>4096</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* System Prompt */}
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="text-sm">System Prompt</CardTitle>
                        <CardDescription>
                          Define the AI's personality and behavior
                        </CardDescription>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setCustomPromptOpen(true)}
                      >
                        <Plus className="w-4 h-4 mr-1" />
                        Custom
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <Select
                      value={settings.systemPromptTemplate}
                      onValueChange={(value) => {
                        const template = allPrompts.find(p => p.id === value);
                        if (template) {
                          handleSettingChange('systemPrompt', template.prompt);
                          handleSettingChange('systemPromptTemplate', value);
                        }
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {allPrompts.map((template) => (
                          <SelectItem key={template.id} value={template.id}>
                            <div className="flex items-center gap-2">
                              {template.icon}
                              <div>
                                <div className="font-medium">{template.name}</div>
                                <div className="text-xs text-muted-foreground">
                                  {template.description}
                                </div>
                              </div>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Textarea
                      value={settings.systemPrompt}
                      onChange={(e) => handleSettingChange('systemPrompt', e.target.value)}
                      className="min-h-[100px]"
                      placeholder="Enter custom system prompt..."
                    />
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="behavior" className="space-y-6">
                {/* Response Settings */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Response Settings</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label>Stream responses</Label>
                        <p className="text-xs text-muted-foreground">
                          See responses as they're being generated
                        </p>
                      </div>
                      <Switch
                        checked={settings.streamResponses}
                        onCheckedChange={(checked) => handleSettingChange('streamResponses', checked)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label>Show thinking process</Label>
                        <p className="text-xs text-muted-foreground">
                          Display the AI's reasoning steps
                        </p>
                      </div>
                      <Switch
                        checked={settings.showThinking}
                        onCheckedChange={(checked) => handleSettingChange('showThinking', checked)}
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
                        onCheckedChange={(checked) => handleSettingChange('autoSave', checked)}
                      />
                    </div>
                  </CardContent>
                </Card>

                {/* Display Options */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Display Options</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label>Show timestamps</Label>
                        <p className="text-xs text-muted-foreground">
                          Display message timestamps
                        </p>
                      </div>
                      <Switch
                        checked={settings.showTimestamps}
                        onCheckedChange={(checked) => handleSettingChange('showTimestamps', checked)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label>Markdown rendering</Label>
                        <p className="text-xs text-muted-foreground">
                          Enable markdown formatting
                        </p>
                      </div>
                      <Switch
                        checked={settings.markdownRendering}
                        onCheckedChange={(checked) => handleSettingChange('markdownRendering', checked)}
                      />
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="appearance" className="space-y-6">
                {/* Theme */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Theme</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { value: 'light', label: 'Light', icon: <Sun className="w-4 h-4" /> },
                        { value: 'dark', label: 'Dark', icon: <Moon className="w-4 h-4" /> },
                        { value: 'system', label: 'System', icon: <Globe className="w-4 h-4" /> },
                      ].map((theme) => (
                        <Button
                          key={theme.value}
                          variant={settings.theme === theme.value ? 'default' : 'outline'}
                          className="h-12"
                          onClick={() => handleSettingChange('theme', theme.value)}
                        >
                          <div className="flex items-center gap-2">
                            {theme.icon}
                            <span>{theme.label}</span>
                          </div>
                        </Button>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* Font & Layout */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Font & Layout</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <Label>Font Size</Label>
                      <Select
                        value={settings.fontSize}
                        onValueChange={(value: any) => handleSettingChange('fontSize', value)}
                      >
                        <SelectTrigger className="mt-2">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="small">Small</SelectItem>
                          <SelectItem value="medium">Medium</SelectItem>
                          <SelectItem value="large">Large</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label>Compact mode</Label>
                        <p className="text-xs text-muted-foreground">
                          Reduce spacing between messages
                        </p>
                      </div>
                      <Switch
                        checked={settings.compactMode}
                        onCheckedChange={(checked) => handleSettingChange('compactMode', checked)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label>Show avatars</Label>
                        <p className="text-xs text-muted-foreground">
                          Display user and assistant avatars
                        </p>
                      </div>
                      <Switch
                        checked={settings.showAvatars}
                        onCheckedChange={(checked) => handleSettingChange('showAvatars', checked)}
                      />
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="privacy" className="space-y-6">
                {/* Data & Storage */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Data & Storage</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <Label>Data Retention (days)</Label>
                      <div className="mt-2">
                        <Slider
                          value={[settings.dataRetention]}
                          onValueChange={([value]) => handleSettingChange('dataRetention', value)}
                          min={7}
                          max={365}
                          step={7}
                          className="mb-2"
                        />
                        <div className="flex justify-between text-xs text-muted-foreground">
                          <span>7 days</span>
                          <span className="font-medium">{settings.dataRetention} days</span>
                          <span>365 days</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label>Share analytics</Label>
                        <p className="text-xs text-muted-foreground">
                          Help improve the service by sharing usage data
                        </p>
                      </div>
                      <Switch
                        checked={settings.shareAnalytics}
                        onCheckedChange={(checked) => handleSettingChange('shareAnalytics', checked)}
                      />
                    </div>
                  </CardContent>
                </Card>

                {/* Notifications */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Notifications</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label>Sound effects</Label>
                        <p className="text-xs text-muted-foreground">
                          Play sounds for messages and interactions
                        </p>
                      </div>
                      <Switch
                        checked={settings.soundEnabled}
                        onCheckedChange={(checked) => handleSettingChange('soundEnabled', checked)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label>Desktop notifications</Label>
                        <p className="text-xs text-muted-foreground">
                          Show system notifications for new messages
                        </p>
                      </div>
                      <Switch
                        checked={settings.desktopNotifications}
                        onCheckedChange={(checked) => handleSettingChange('desktopNotifications', checked)}
                      />
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </div>
          </Tabs>
        </div>

        {/* Actions */}
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={handleReset}>
            <RotateCcw className="w-4 h-4 mr-2" />
            Reset to Default
          </Button>
          <div className="flex gap-2">
            <label>
              <Button variant="outline" asChild>
                <span>
                  <Upload className="w-4 h-4 mr-2" />
                  Import
                </span>
              </Button>
              <input
                type="file"
                accept=".json"
                onChange={handleImport}
                className="hidden"
              />
            </label>
            <Button variant="outline" onClick={handleExport}>
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
          </div>
          <Button onClick={() => onOpenChange(false)}>
            <Save className="w-4 h-4 mr-2" />
            Save Settings
          </Button>
        </DialogFooter>
      </DialogContent>

      {/* Custom Prompt Dialog */}
      <Dialog open={customPromptOpen} onOpenChange={setCustomPromptOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Custom Prompt</DialogTitle>
            <DialogDescription>
              Save a custom system prompt for future use
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Name</Label>
              <Input
                value={customPromptName}
                onChange={(e) => setCustomPromptName(e.target.value)}
                placeholder="e.g., Legal Expert, Creative Partner"
              />
            </div>
            <div>
              <Label>Prompt</Label>
              <Textarea
                value={customPromptContent}
                onChange={(e) => setCustomPromptContent(e.target.value)}
                placeholder="Enter the system prompt..."
                className="min-h-[100px]"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCustomPromptOpen(false)}>
              Cancel
            </Button>
            <Button onClick={saveCustomPrompt} disabled={!customPromptName || !customPromptContent}>
              <Save className="w-4 h-4 mr-2" />
              Save Prompt
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Dialog>
  );
}

export default ChatSettingsPanel;