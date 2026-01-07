'use client';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
// import { useTambo, useTamboThreadInput } from '@tambo-ai/react';
import { AnimatePresence, motion } from 'framer-motion';
import {
    Brain,
    FileText,
    Lightbulb,
    Loader2,
    Send,
    Sparkles,
    TrendingUp,
    Zap
} from 'lucide-react';
import React, { useState } from 'react';

interface InsightItem {
  id: string;
  type: 'suggestion' | 'discovery' | 'alert';
  title: string;
  description: string;
}

// Sample insights for demonstration
const sampleInsights: InsightItem[] = [
  {
    id: '1',
    type: 'discovery',
    title: 'Related Documents Found',
    description: '3 documents share similar topics about "machine learning optimization"',
  },
  {
    id: '2',
    type: 'suggestion',
    title: 'Recommended Search',
    description: 'Try searching for "neural network architectures" based on your recent activity',
  },
  {
    id: '3',
    type: 'alert',
    title: 'New Insights Available',
    description: 'AI has analyzed your latest uploads and found key entities',
  },
];

const insightConfig = {
  suggestion: {
    icon: Lightbulb,
    color: 'text-amber-500',
    bgColor: 'bg-gradient-to-br from-amber-500/10 to-orange-500/10',
    borderColor: 'border-amber-500/20',
    hoverBg: 'hover:from-amber-500/20 hover:to-orange-500/20',
  },
  discovery: {
    icon: FileText,
    color: 'text-blue-500',
    bgColor: 'bg-gradient-to-br from-blue-500/10 to-indigo-500/10',
    borderColor: 'border-blue-500/20',
    hoverBg: 'hover:from-blue-500/20 hover:to-indigo-500/20',
  },
  alert: {
    icon: TrendingUp,
    color: 'text-emerald-500',
    bgColor: 'bg-gradient-to-br from-emerald-500/10 to-teal-500/10',
    borderColor: 'border-emerald-500/20',
    hoverBg: 'hover:from-emerald-500/20 hover:to-teal-500/20',
  },
};

interface AIInsightsPanelProps {
  className?: string;
}

export function AIInsightsPanel({ className }: AIInsightsPanelProps) {
  // const { isIdle } = useTambo();
  // const { value, setValue, submit, isPending } = useTamboThreadInput();
  const isIdle = true;
  const isPending = false;
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [value, setValue] = useState('');
  const submit = async (_options?: { streamResponse: boolean }) => {
     console.log('Tambo submit disabled');
     return Promise.resolve();
  };
  const [isExpanded, setIsExpanded] = useState(false);
  const [localInput, setLocalInput] = useState('');
  const [hoveredInsight, setHoveredInsight] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!localInput.trim() || isPending) return;

    setValue(localInput);
    try {
      await submit({ streamResponse: true });
      setLocalInput('');
    } catch (error) {
      console.error('Failed to submit:', error);
    }
  };

  const handleQuickQuestion = async (question: string) => {
    setValue(question);
    try {
      await submit({ streamResponse: true });
    } catch (error) {
      console.error('Failed to submit:', error);
    }
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.2,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        type: "spring" as const,
        stiffness: 100,
        damping: 10,
      },
    },
  };

  return (
    <motion.div
      className={cn(
        'relative overflow-hidden rounded-2xl border border-border/50',
        'bg-gradient-to-br from-card/60 via-card/40 to-card/20 backdrop-blur-sm',
        className
      )}
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Animated background effect */}
      <div className="absolute inset-0 opacity-50">
        <motion.div
          className="absolute inset-0 bg-gradient-to-r from-amber-500/5 via-orange-500/5 to-amber-500/5"
          animate={{
            x: [0, 100, 0],
            opacity: [0.3, 0.7, 0.3],
          }}
          transition={{
            duration: 10,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(251,191,36,0.15),transparent_60%)]" />
      </div>

      {/* Glass reflection effect */}
      <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent opacity-0 hover:opacity-100 transition-opacity duration-700" />

      {/* Header */}
      <div className="relative border-b border-border/50">
        <motion.div
          className="relative flex items-center justify-between p-6"
          variants={itemVariants}
        >
          <div className="flex items-center gap-4">
            <motion.div
              className="relative"
              whileHover={{
                scale: 1.1,
                rotate: [0, -5, 5, 0],
              }}
              transition={{ duration: 0.3 }}
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-500 to-orange-500 shadow-lg shadow-amber-500/25 border border-amber-500/30">
                <motion.div
                  animate={{
                    rotate: [0, 360]
                  }}
                  transition={{
                    duration: 8,
                    repeat: Infinity,
                    ease: "linear",
                    repeatDelay: 3
                  }}
                >
                  <Sparkles className="h-6 w-6 text-white" />
                </motion.div>
              </div>
              <AnimatePresence>
                {!isIdle && (
                  <motion.span
                    className="absolute -bottom-1 -right-1 h-4 w-4 rounded-full border-2 border-card bg-amber-500"
                    initial={{ scale: 0 }}
                    animate={{ scale: [1, 1.2, 1] }}
                    exit={{ scale: 0 }}
                    transition={{ duration: 0.5, repeat: Infinity }}
                  />
                )}
              </AnimatePresence>
            </motion.div>
            <div>
              <motion.h3
                className="text-lg font-semibold text-foreground flex items-center gap-3"
                variants={itemVariants}
              >
                <span className="bg-gradient-to-r from-amber-600 to-orange-600 bg-clip-text text-transparent">
                  AI Insights
                </span>
                <AnimatePresence>
                  {!isIdle && (
                    <motion.span
                      className="text-sm font-normal text-amber-600 flex items-center gap-1"
                      initial={{ opacity: 0, x: 10 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 10 }}
                    >
                      <motion.div
                        className="w-2 h-2 bg-amber-500 rounded-full"
                        animate={{
                          scale: [1, 1.5, 1],
                          opacity: [1, 0.7, 1],
                        }}
                        transition={{ duration: 2, repeat: Infinity }}
                      />
                      Thinking...
                    </motion.span>
                  )}
                </AnimatePresence>
              </motion.h3>
              <motion.p
                className="text-sm text-muted-foreground flex items-center gap-2"
                variants={itemVariants}
              >
                <Brain className="h-3 w-3 text-amber-500" />
                Powered by Tambo AI
              </motion.p>
            </div>
          </div>
          <motion.div
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-xs backdrop-blur-sm bg-card/50 hover:bg-card/70 border border-border/30"
            >
              <motion.div
                animate={{ rotate: isExpanded ? 180 : 0 }}
                transition={{ duration: 0.3 }}
              >
                ▼
              </motion.div>
              {isExpanded ? 'Collapse' : 'Expand'}
            </Button>
          </motion.div>
        </motion.div>
      </div>

      {/* Insights List */}
      <div className="divide-y divide-border/30">
        {sampleInsights.map((insight, index) => {
          const config = insightConfig[insight.type];
          const Icon = config.icon;

          return (
            <motion.div
              key={insight.id}
              className="relative group"
              variants={itemVariants}
              onHoverStart={() => setHoveredInsight(insight.id)}
              onHoverEnd={() => setHoveredInsight(null)}
              onClick={() => handleQuickQuestion(`Tell me more about: ${insight.title}`)}
            >
              <div className="flex items-start gap-4 p-6 cursor-pointer">
                <motion.div
                  className={cn(
                    'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border',
                    config.bgColor,
                    config.borderColor,
                    config.hoverBg,
                    'transition-all duration-300'
                  )}
                  whileHover={{
                    scale: 1.1,
                    rotate: 5,
                  }}
                >
                  <motion.div
                    animate={{
                      rotate: [0, -10, 10, 0],
                    }}
                    transition={{
                      duration: 4,
                      repeat: Infinity,
                      repeatDelay: 2,
                    }}
                  >
                    <Icon className={cn('h-5 w-5', config.color)} />
                  </motion.div>
                </motion.div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <motion.p
                      className="text-sm font-semibold text-foreground"
                      animate={{
                        color: hoveredInsight === insight.id ? '#f59e0b' : 'inherit',
                      }}
                    >
                      {insight.title}
                    </motion.p>
                    <motion.div
                      className="opacity-0 group-hover:opacity-100 transition-opacity"
                      initial={{ scale: 0 }}
                      whileHover={{ scale: 1 }}
                    >
                      <Zap className="h-4 w-4 text-amber-500" />
                    </motion.div>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                    {insight.description}
                  </p>
                </div>
              </div>

              {/* Hover effect overlay */}
              <motion.div
                className="absolute inset-0 bg-gradient-to-r from-amber-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
                initial={{ x: '-100%' }}
                whileHover={{ x: 0 }}
                transition={{ duration: 0.3 }}
              />
            </motion.div>
          );
        })}
      </div>

      {/* Quick Input with Enhanced Animation */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            className="border-t border-border/50 bg-gradient-to-br from-muted/30 to-muted/10 backdrop-blur-sm"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
          >
            <div className="p-6">
              <motion.form
                onSubmit={handleSubmit}
                className="flex gap-3"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
              >
                <div className="relative flex-1">
                  <motion.input
                    type="text"
                    value={localInput}
                    onChange={(e) => setLocalInput(e.target.value)}
                    placeholder="Ask AI about your documents..."
                    className={cn(
                      'w-full rounded-xl border border-border/50 bg-card/50 backdrop-blur-sm px-4 py-3 text-sm',
                      'placeholder:text-muted-foreground/70',
                      'focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500/50',
                      'transition-all duration-300'
                    )}
                    disabled={isPending}
                    whileFocus={{
                      scale: 1.01,
                      borderColor: '#f59e0b',
                    }}
                  />
                  {/* Floating particles in input */}
                  <AnimatePresence>
                    {localInput && (
                      <div className="absolute inset-0 overflow-hidden rounded-xl pointer-events-none">
                        {[...Array(3)].map((_, i) => (
                          <motion.div
                            key={i}
                            className="absolute w-1 h-1 bg-amber-500/30 rounded-full"
                            animate={{
                              x: [0, Math.random() * 100],
                              y: [0, Math.random() * 40 - 20],
                              opacity: [0, 1, 0],
                            }}
                            transition={{
                              duration: 2 + Math.random(),
                              repeat: Infinity,
                              delay: Math.random(),
                            }}
                            style={{
                              left: `${Math.random() * 80 + 10}%`,
                              top: `${Math.random() * 60 + 20}%`,
                            }}
                          />
                        ))}
                      </div>
                    )}
                  </AnimatePresence>
                </div>
                <motion.div
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <Button
                    type="submit"
                    size="sm"
                    disabled={isPending || !localInput.trim()}
                    className="bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white border-0 shadow-lg shadow-amber-500/25 rounded-xl px-6"
                  >
                    <AnimatePresence mode="wait">
                      {isPending ? (
                        <motion.div
                          key="loading"
                          initial={{ rotate: 0 }}
                          animate={{ rotate: 360 }}
                          exit={{ rotate: 0 }}
                          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                        >
                          <Loader2 className="h-4 w-4" />
                        </motion.div>
                      ) : (
                        <motion.div
                          key="send"
                          initial={{ scale: 0.8 }}
                          animate={{ scale: 1 }}
                          exit={{ scale: 0.8 }}
                        >
                          <Send className="h-4 w-4" />
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </Button>
                </motion.div>
              </motion.form>

              <motion.div
                className="flex gap-4 mt-4"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
              >
                {[
                  { text: '📄 Summarize docs', question: 'Summarize my recent documents' },
                  { text: '💡 Find insights', question: 'What insights can you find?' },
                  { text: '🔗 Related topics', question: 'Suggest related topics' },
                ].map((item, index) => (
                  <motion.button
                    key={item.text}
                    type="button"
                    onClick={() => handleQuickQuestion(item.question)}
                    className="text-xs text-muted-foreground hover:text-amber-600 transition-colors duration-200 flex items-center gap-1"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.3 + index * 0.1 }}
                  >
                    {item.text}
                  </motion.button>
                ))}
              </motion.div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
