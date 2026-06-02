'use client';

import * as React from 'react';
import { useState, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  Sparkles,
  Bot,
  Code,
  PenTool,
  Briefcase,
  ChevronRight,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';

export interface Assistant {
  id: string;
  name: string;
  description: string;
  avatar: string;
  category: string;
  capabilities: string[];
  color: string;
}

interface NewChatDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  assistants: Assistant[];
  onSelectAssistant: (assistant: Assistant) => void;
  isLoading?: boolean;
}

const defaultAssistants: Assistant[] = [
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
];

const categoryIcons = {
  general: Sparkles,
  development: Code,
  creative: PenTool,
  business: Briefcase,
};

const AssistantCard = React.forwardRef<
  HTMLDivElement,
  {
    assistant: Assistant;
    isSelected: boolean;
    onSelect: () => void;
  }
>(({ assistant, isSelected, onSelect }, ref) => {
  const CategoryIcon =
    categoryIcons[assistant.category as keyof typeof categoryIcons] || Sparkles;

  return (
    <motion.div
      ref={ref}
      whileHover={{ y: -2, scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
    >
      <div
        onClick={onSelect}
        className={cn(
          'relative p-4 rounded-xl cursor-pointer transition-all duration-300 border',
          'backdrop-blur-md bg-white/10 dark:bg-black/10',
          'hover:bg-white/20 dark:hover:bg-black/20',
          'hover:shadow-lg hover:shadow-orange-500/10',
          isSelected && [
            'border-orange-400/50 bg-gradient-to-r from-orange-500/10 to-amber-500/10',
            'shadow-lg shadow-orange-500/20',
            'ring-2 ring-orange-400/50 ring-offset-2 ring-offset-background',
          ],
          !isSelected && 'border-border/50 hover:border-orange-300/30'
        )}
      >
        <div className="flex items-start gap-4">
          <motion.div
            className="relative"
            whileHover={{ rotate: 5 }}
            transition={{ type: 'spring', stiffness: 300 }}
          >
            <Avatar className="h-12 w-12 ring-2 ring-background/50">
              <AvatarImage src={assistant.avatar} alt={assistant.name} />
              <AvatarFallback
                className={`bg-gradient-to-br ${assistant.color} text-white font-semibold`}
              >
                {assistant.name.slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div className="absolute -bottom-1 -right-1 h-4 w-4 rounded-full bg-gradient-to-br from-orange-400 to-amber-500 flex items-center justify-center">
              <CategoryIcon className="h-2 w-2 text-white" />
            </div>
          </motion.div>

          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-foreground mb-1 flex items-center gap-2">
              {assistant.name}
              {isSelected && (
                <motion.div
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                >
                  <div className="h-2 w-2 rounded-full bg-orange-400" />
                </motion.div>
              )}
            </h3>
            <p className="text-sm text-muted-foreground mb-2 line-clamp-2">
              {assistant.description}
            </p>
            <div className="flex flex-wrap gap-1">
              {assistant.capabilities.slice(0, 3).map((capability) => (
                <span
                  key={capability}
                  className="text-xs px-2 py-1 rounded-full bg-primary/10 text-primary/70"
                >
                  {capability}
                </span>
              ))}
              {assistant.capabilities.length > 3 && (
                <span className="text-xs px-2 py-1 rounded-full bg-muted text-muted-foreground">
                  +{assistant.capabilities.length - 3}
                </span>
              )}
            </div>
          </div>

          {isSelected && (
            <motion.div
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ type: 'spring', stiffness: 400, damping: 25 }}
              className="text-orange-400"
            >
              <ChevronRight className="h-5 w-5" />
            </motion.div>
          )}
        </div>
      </div>
    </motion.div>
  );
});

AssistantCard.displayName = 'AssistantCard';

export function NewChatDialog({
  open,
  onOpenChange,
  assistants = defaultAssistants,
  onSelectAssistant,
  isLoading = false,
}: NewChatDialogProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedAssistant, setSelectedAssistant] = useState<string | null>(
    null
  );

  const filteredAssistants = useMemo(() => {
    if (!searchQuery) return assistants;

    const query = searchQuery.toLowerCase();
    return assistants.filter(
      (assistant) =>
        assistant.name.toLowerCase().includes(query) ||
        assistant.description.toLowerCase().includes(query) ||
        assistant.capabilities.some((cap) =>
          cap.toLowerCase().includes(query)
        ) ||
        assistant.category.toLowerCase().includes(query)
    );
  }, [assistants, searchQuery]);

  const handleSelectAssistant = useCallback((assistant: Assistant) => {
    setSelectedAssistant(assistant.id);
  }, []);

  const handleStartChat = useCallback(() => {
    if (selectedAssistant) {
      const assistant = assistants.find((a) => a.id === selectedAssistant);
      if (assistant) {
        onSelectAssistant(assistant);
        onOpenChange(false);
        setSelectedAssistant(null);
        setSearchQuery('');
      }
    }
  }, [selectedAssistant, assistants, onSelectAssistant, onOpenChange]);

  const handleDialogChange = useCallback(
    (open: boolean) => {
      if (!open) {
        setSelectedAssistant(null);
        setSearchQuery('');
      }
      onOpenChange(open);
    },
    [onOpenChange]
  );

  return (
    <Dialog open={open} onOpenChange={handleDialogChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-2xl">
              <div className="p-2 rounded-lg bg-gradient-to-br from-orange-400 to-amber-500 text-white">
                <Sparkles className="h-5 w-5" />
              </div>
              New Chat
            </DialogTitle>
            <DialogDescription className="text-base">
              Start a new conversation with one of our specialized AI assistants
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Search Input */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search assistants by name, capability, or category..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 h-12 bg-background/50 backdrop-blur-sm border-border/50 focus:border-orange-400/50 transition-colors"
                />
                {searchQuery && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSearchQuery('')}
                    className="absolute right-1 top-1/2 -translate-y-1/2 h-8 w-8 p-0"
                  >
                    ×
                  </Button>
                )}
              </div>
            </motion.div>

            {/* Assistant Grid */}
            <div className="max-h-[50vh] overflow-y-auto pr-2 -mr-2 scrollbar-thin scrollbar-thumb-orange-200 scrollbar-track-transparent">
              {isLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-orange-400" />
                </div>
              ) : filteredAssistants.length === 0 ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-center py-12"
                >
                  <Bot className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">
                    No assistants found matching your search
                  </p>
                </motion.div>
              ) : (
                <motion.div layout className="grid gap-3">
                  <AnimatePresence mode="popLayout">
                    {filteredAssistants.map((assistant, index) => (
                      <motion.div
                        key={assistant.id}
                        layout
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        transition={{
                          delay: index * 0.05,
                          type: 'spring',
                          stiffness: 400,
                          damping: 25,
                        }}
                      >
                        <AssistantCard
                          assistant={assistant}
                          isSelected={selectedAssistant === assistant.id}
                          onSelect={() => handleSelectAssistant(assistant)}
                        />
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </motion.div>
              )}
            </div>

            {/* Action Button */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="pt-4 border-t border-border/50"
            >
              <Button
                onClick={handleStartChat}
                disabled={!selectedAssistant || isLoading}
                className="w-full h-12 bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white font-medium shadow-lg shadow-orange-500/25 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Loading...
                  </>
                ) : (
                  <>
                    Start Chat
                    <ChevronRight className="h-4 w-4 ml-2" />
                  </>
                )}
              </Button>
            </motion.div>
          </div>
        </motion.div>
      </DialogContent>
    </Dialog>
  );
}
