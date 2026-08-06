'use client';

import * as React from 'react';
import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { motion, AnimatePresence, useAnimation } from 'framer-motion';
import {
  Search,
  Sparkles,
  Bot,
  Code,
  PenTool,
  Briefcase,
  ChevronRight,
  Loader2,
  AlertCircle,
  TrendingUp,
  Clock,
  Star,
  Zap,
  Shield,
  Globe,
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
import { Badge } from '@/components/ui/badge';
import { Assistant, AssistantCategory } from '@/types/chat';

interface EnhancedNewChatDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  assistants: Assistant[];
  onSelectAssistant: (assistant: Assistant) => void;
  isLoading?: boolean;
  error?: string | null;
  categories?: AssistantCategory[];
  showCategories?: boolean;
  showTrending?: boolean;
  recentlyUsed?: Assistant[];
}

const categoryIcons: Record<
  string,
  React.ComponentType<{ className?: string }>
> = {
  general: Sparkles,
  development: Code,
  creative: PenTool,
  business: Briefcase,
  academic: TrendingUp,
  health: Shield,
};

const glassVariants = {
  hidden: { opacity: 0, backdropFilter: 'blur(0px)' },
  visible: {
    opacity: 1,
    backdropFilter: 'blur(16px) saturate(180%)',
    transition: { duration: 0.3, ease: 'easeOut' },
  },
  exit: {
    opacity: 0,
    backdropFilter: 'blur(0px)',
    transition: { duration: 0.2, ease: 'easeIn' },
  },
};

const EnhancedAssistantCard = React.forwardRef<
  HTMLDivElement,
  {
    assistant: Assistant;
    isSelected: boolean;
    onSelect: () => void;
    showMetrics?: boolean;
    variant?: 'default' | 'compact' | 'detailed';
  }
>(
  (
    {
      assistant,
      isSelected,
      onSelect,
      showMetrics = true,
      variant = 'default',
    },
    ref
  ) => {
    const CategoryIcon = categoryIcons[assistant.category] || Sparkles;
    const [isHovered, setIsHovered] = useState(false);

    return (
      <motion.div
        ref={ref}
        whileHover={{ y: -4, scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onHoverStart={() => setIsHovered(true)}
        onHoverEnd={() => setIsHovered(false)}
        transition={{ type: 'spring', stiffness: 400, damping: 25 }}
        layout
      >
        <button
          type="button"
          onClick={onSelect}
          aria-pressed={isSelected}
          aria-label={`Select ${assistant.name}`}
          className={cn(
            'w-full text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-400/50',
            'relative overflow-hidden rounded-xl cursor-pointer transition-all duration-300 border-2',
            'backdrop-blur-md bg-white/10 dark:bg-black/10',
            'hover:bg-white/20 dark:hover:bg-black/20',
            'hover:shadow-xl hover:shadow-orange-500/20',
            isSelected && [
              'border-orange-400/50 bg-gradient-to-br from-orange-500/10 via-amber-500/5 to-transparent',
              'shadow-2xl shadow-orange-500/30',
              'ring-4 ring-orange-400/20 ring-offset-2 ring-offset-background',
            ],
            !isSelected && 'border-border/30 hover:border-orange-300/50'
          )}
        >
          {/* Animated background gradient */}
          <AnimatePresence>
            {isSelected && (
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                className="absolute inset-0 bg-gradient-to-br from-orange-500/10 to-amber-500/5"
              />
            )}
          </AnimatePresence>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="relative p-6"
          >
            <div className="flex items-start gap-4">
              {/* Avatar with animated ring */}
              <motion.div
                className="relative"
                whileHover={{ rotate: [0, -5, 5, 0] }}
                transition={{ duration: 0.5, repeat: Infinity, repeatDelay: 2 }}
              >
                <motion.div
                  className={cn(
                    'absolute inset-0 rounded-full bg-gradient-to-br opacity-0',
                    isSelected
                      ? 'from-orange-400 to-amber-500 opacity-30'
                      : `${assistant.color} opacity-20`
                  )}
                  animate={isSelected ? { scale: [1, 1.2, 1] } : {}}
                  transition={{ duration: 2, repeat: Infinity }}
                />
                <Avatar className="h-14 w-14 ring-2 ring-background/50 relative">
                  <AvatarImage src={assistant.avatar} alt={assistant.name} />
                  <AvatarFallback
                    className={`bg-gradient-to-br ${assistant.color} text-white font-bold text-lg`}
                  >
                    {assistant.name.slice(0, 2).toUpperCase()}
                  </AvatarFallback>
                </Avatar>

                {/* Category badge */}
                <motion.div
                  className="absolute -bottom-1 -right-1 h-5 w-5 rounded-full bg-gradient-to-br from-orange-400 to-amber-500 flex items-center justify-center"
                  initial={{ scale: 0, rotate: -180 }}
                  animate={{ scale: 1, rotate: 0 }}
                  transition={{ delay: 0.2, type: 'spring', stiffness: 500 }}
                >
                  <CategoryIcon className="h-3 w-3 text-white" />
                </motion.div>
              </motion.div>

              {/* Content */}
              <div className="flex-1 min-w-0 space-y-2">
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-lg text-foreground">
                    {assistant.name}
                  </h3>
                  {assistant.isPremium && (
                    <Badge
                      variant="secondary"
                      className="bg-gradient-to-r from-yellow-400 to-amber-500 text-white border-0"
                    >
                      <Zap className="h-3 w-3 mr-1" />
                      PRO
                    </Badge>
                  )}
                  {assistant.isActive && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: [1, 1.2, 1] }}
                      transition={{ duration: 2, repeat: Infinity }}
                      className="h-2 w-2 rounded-full bg-green-400"
                    />
                  )}
                </div>

                <p className="text-sm text-muted-foreground leading-relaxed">
                  {assistant.description}
                </p>

                {/* Capabilities */}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {assistant.capabilities
                    .slice(0, 3)
                    .map((capability, index) => (
                      <Badge
                        key={index}
                        variant="outline"
                        className="text-xs px-2 py-0.5 bg-primary/5 border-primary/20 hover:bg-primary/10"
                      >
                        {capability}
                      </Badge>
                    ))}
                  {assistant.capabilities.length > 3 && (
                    <span className="text-xs text-muted-foreground px-2 py-0.5">
                      +{assistant.capabilities.length - 3} more
                    </span>
                  )}
                </div>

                {/* Metrics */}
                {showMetrics && variant !== 'compact' && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="flex items-center gap-4 text-xs text-muted-foreground pt-2"
                  >
                    {assistant.usageCount && (
                      <span className="flex items-center gap-1">
                        <TrendingUp className="h-3 w-3" />
                        {assistant.usageCount.toLocaleString()} uses
                      </span>
                    )}
                    {assistant.avgRating && (
                      <span className="flex items-center gap-1">
                        <Star className="h-3 w-3 fill-orange-400 text-orange-400" />
                        {assistant.avgRating.toFixed(1)}
                      </span>
                    )}
                    {assistant.model && (
                      <span className="flex items-center gap-1">
                        <Bot className="h-3 w-3" />
                        {assistant.model}
                      </span>
                    )}
                  </motion.div>
                )}
              </div>

              {/* Selection indicator */}
              <AnimatePresence>
                {isSelected && (
                  <motion.div
                    initial={{ scale: 0, opacity: 0, rotate: -180 }}
                    animate={{ scale: 1, opacity: 1, rotate: 0 }}
                    exit={{ scale: 0, opacity: 0, rotate: 180 }}
                    transition={{ type: 'spring', stiffness: 500 }}
                    className="text-orange-400"
                  >
                    <ChevronRight className="h-6 w-6" />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>

          {/* Hover effect overlay */}
          <AnimatePresence>
            {isHovered && !isSelected && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 bg-gradient-to-br from-orange-500/5 to-amber-500/5 pointer-events-none"
              />
            )}
          </AnimatePresence>
        </button>
      </motion.div>
    );
  }
);

EnhancedAssistantCard.displayName = 'EnhancedAssistantCard';

export function EnhancedNewChatDialog({
  open,
  onOpenChange,
  assistants,
  onSelectAssistant,
  isLoading = false,
  error = null,
  categories = [],
  showCategories = true,
  showTrending = true,
  recentlyUsed = [],
}: EnhancedNewChatDialogProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedAssistant, setSelectedAssistant] = useState<string | null>(
    null
  );
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const controls = useAnimation();
  const autoSelectedRef = useRef(false);

  // Reset state when dialog opens/closes
  useEffect(() => {
    if (open) {
      controls.start('visible');
      // Auto-select first recently used assistant only once per open cycle.
      // Using a ref instead of selectedAssistant in the dep array avoids a
      // re-render loop (selectedAssistant set inside the effect ↔ dep change).
      if (recentlyUsed.length > 0 && !autoSelectedRef.current) {
        autoSelectedRef.current = true;
        setSelectedAssistant(recentlyUsed[0].id);
      }
    } else {
      controls.start('exit');
      autoSelectedRef.current = false;
      setSelectedAssistant(null);
      setSearchQuery('');
      setSelectedCategory(null);
    }
  }, [open, controls, recentlyUsed]);

  const filteredAssistants = useMemo(() => {
    let filtered = assistants;

    // Filter by category
    if (selectedCategory) {
      filtered = filtered.filter((a) => a.category === selectedCategory);
    }

    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (assistant) =>
          assistant.name.toLowerCase().includes(query) ||
          assistant.description.toLowerCase().includes(query) ||
          assistant.capabilities.some((cap) =>
            cap.toLowerCase().includes(query)
          ) ||
          assistant.category.toLowerCase().includes(query)
      );
    }

    // Sort: recently used first, then by usage count, then alphabetically
    filtered.sort((a, b) => {
      const aRecent = recentlyUsed.findIndex((r) => r.id === a.id);
      const bRecent = recentlyUsed.findIndex((r) => r.id === b.id);

      if (aRecent !== -1 && bRecent !== -1) return aRecent - bRecent;
      if (aRecent !== -1) return -1;
      if (bRecent !== -1) return 1;

      return (b.usageCount || 0) - (a.usageCount || 0);
    });

    return filtered;
  }, [assistants, searchQuery, selectedCategory, recentlyUsed]);

  const handleSelectAssistant = useCallback((assistant: Assistant) => {
    setSelectedAssistant(assistant.id);
  }, []);

  const handleStartChat = useCallback(() => {
    if (selectedAssistant) {
      const assistant = assistants.find((a) => a.id === selectedAssistant);
      if (assistant) {
        onSelectAssistant(assistant);
        onOpenChange(false);
      }
    }
  }, [selectedAssistant, assistants, onSelectAssistant, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <motion.div variants={glassVariants} animate={controls} initial="hidden">
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden bg-gradient-to-br from-background/95 via-background/90 to-background/95 backdrop-blur-2xl border-border/20">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="space-y-6"
          >
            {/* Header with gradient decoration */}
            <DialogHeader className="text-center pb-4 border-b border-border/10">
              <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: 'spring', stiffness: 500 }}
                className="inline-flex items-center justify-center p-3 rounded-2xl bg-gradient-to-br from-orange-400 to-amber-500 text-white mb-4 mx-auto shadow-lg shadow-orange-500/25"
              >
                <Sparkles className="h-8 w-8" />
              </motion.div>
              <DialogTitle className="text-3xl font-bold text-foreground">
                Start a New Conversation
              </DialogTitle>
              <DialogDescription className="text-base mt-2">
                Choose from our specialized AI assistants tailored to your needs
              </DialogDescription>
            </DialogHeader>

            {/* Error state */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive border border-destructive/20"
                >
                  <AlertCircle className="h-4 w-4" />
                  <span className="text-sm">{error}</span>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Search and filters */}
            <div className="space-y-4">
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 }}
                className="relative"
              >
                <Search
                  className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground"
                  aria-hidden="true"
                />
                <Input
                  placeholder="Search by name, capability, or category..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  aria-label="Search assistants"
                  className="h-12 pl-12 pr-12 text-base bg-background/50 backdrop-blur-sm border-border/50 focus:border-orange-400/50 focus:ring-2 focus:ring-orange-400/20 transition-all duration-300"
                />
                {searchQuery && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSearchQuery('')}
                    aria-label="Clear search"
                    className="absolute right-2 top-1/2 -translate-y-1/2 h-8 w-8 p-0 hover:bg-muted/50"
                  >
                    ×
                  </Button>
                )}
              </motion.div>

              {/* Category filters */}
              {showCategories && categories.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                  className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-hide"
                >
                  <Button
                    variant={!selectedCategory ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setSelectedCategory(null)}
                    className="whitespace-nowrap"
                  >
                    <Globe className="h-4 w-4 mr-1" />
                    All
                  </Button>
                  {categories.map((category) => {
                    const Icon = categoryIcons[category.id] || Sparkles;
                    return (
                      <Button
                        key={category.id}
                        variant={
                          selectedCategory === category.id
                            ? 'default'
                            : 'outline'
                        }
                        size="sm"
                        onClick={() => setSelectedCategory(category.id)}
                        className="whitespace-nowrap"
                      >
                        <Icon className="h-4 w-4 mr-1" />
                        {category.name}
                      </Button>
                    );
                  })}
                </motion.div>
              )}

              {/* Recently used indicator */}
              {recentlyUsed.length > 0 &&
                searchQuery === '' &&
                !selectedCategory && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.3 }}
                    className="flex items-center gap-2 text-sm text-muted-foreground"
                  >
                    <Clock className="h-4 w-4" />
                    Recently used assistants
                  </motion.div>
                )}
            </div>

            {/* Assistant grid */}
            <div className="flex-1 overflow-y-auto pr-2 -mr-2 smooth-scrollbar max-h-[50vh]">
              {isLoading ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex flex-col items-center justify-center py-16"
                >
                  <Loader2 className="h-12 w-12 animate-spin text-orange-400 mb-4" />
                  <p className="text-muted-foreground">Loading assistants...</p>
                </motion.div>
              ) : filteredAssistants.length === 0 ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-center py-16"
                >
                  <Bot className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                  <p className="text-xl text-muted-foreground mb-2">
                    No assistants found
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Try adjusting your search or filters
                  </p>
                </motion.div>
              ) : (
                <motion.div layout className="grid gap-4">
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
                        <EnhancedAssistantCard
                          assistant={assistant}
                          isSelected={selectedAssistant === assistant.id}
                          onSelect={() => handleSelectAssistant(assistant)}
                          showMetrics={showTrending}
                          variant="detailed"
                        />
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </motion.div>
              )}
            </div>

            {/* Action button */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="pt-6 border-t border-border/10"
            >
              <Button
                onClick={handleStartChat}
                disabled={!selectedAssistant || isLoading}
                size="lg"
                className="w-full h-14 text-base font-semibold bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white shadow-lg shadow-orange-500/25 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed group"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-5 w-5 animate-spin mr-2" />
                    Loading...
                  </>
                ) : (
                  <>
                    Start Conversation
                    <motion.div
                      animate={{ x: [0, 5, 0] }}
                      transition={{ duration: 1.5, repeat: Infinity }}
                    >
                      <ChevronRight className="h-5 w-5 ml-2 group-hover:translate-x-1 transition-transform" />
                    </motion.div>
                  </>
                )}
              </Button>
            </motion.div>
          </motion.div>
        </DialogContent>
      </motion.div>
    </Dialog>
  );
}
