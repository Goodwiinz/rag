"use client";

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
// import { useTambo, useTamboThreadInput } from '@tambo-ai/react';
import { AnimatePresence, motion } from 'framer-motion';
import {
    AlertCircle,
    ArrowRight,
    Brain,
    ChevronDown,
    FileText,
    Hash,
    Lightbulb,
    Loader2,
    Plus,
    Send,
    Target,
    Timer,
    Zap
} from 'lucide-react';
import React, { useState } from 'react';

interface InsightItem {
  id: string;
  type: 'suggestion' | 'discovery' | 'alert';
  title: string;
  description: string;
  metadata?: {
    confidence: number;
    timestamp: string;
    tags: string[];
  };
}

const sampleInsights: InsightItem[] = [
  {
    id: '1',
    type: 'discovery',
    title: 'Related Documents Found',
    description: '3 documents share similar topics about "machine learning optimization"',
    metadata: {
      confidence: 92,
      timestamp: '2 min ago',
      tags: ['ML', 'Optimization', 'Research'],
    },
  },
  {
    id: '2',
    type: 'suggestion',
    title: 'Recommended Search',
    description: 'Try searching for "neural network architectures" based on your recent activity',
    metadata: {
      confidence: 87,
      timestamp: '5 min ago',
      tags: ['Search', 'Recommendation'],
    },
  },
  {
    id: '3',
    type: 'alert',
    title: 'New Insights Available',
    description: 'AI has analyzed your latest uploads and found key entities',
    metadata: {
      confidence: 95,
      timestamp: 'Just now',
      tags: ['Entities', 'Analysis'],
    },
  },
];

const insightConfig = {
  suggestion: {
    icon: Lightbulb,
    color: 'text-amber-500',
    bgColor: 'bg-gradient-to-br from-amber-500/10 to-orange-500/10',
    borderColor: 'border-amber-500/20',
    hoverBg: 'hover:from-amber-500/20 hover:to-orange-500/20',
    progressColor: 'from-amber-400 to-orange-500',
  },
  discovery: {
    icon: FileText,
    color: 'text-blue-500',
    bgColor: 'bg-gradient-to-br from-blue-500/10 to-indigo-500/10',
    borderColor: 'border-blue-500/20',
    hoverBg: 'hover:from-blue-500/20 hover:to-indigo-500/20',
    progressColor: 'from-blue-400 to-indigo-500',
  },
  alert: {
    icon: AlertCircle,
    color: 'text-emerald-500',
    bgColor: 'bg-gradient-to-br from-emerald-500/10 to-teal-500/10',
    borderColor: 'border-emerald-500/20',
    hoverBg: 'hover:from-emerald-500/20 hover:to-teal-500/20',
    progressColor: 'from-emerald-400 to-teal-500',
  },
};

interface AIInsightsPanelProps {
  className?: string;
}

export function AIInsightsPanelEnhanced({ className }: AIInsightsPanelProps) {
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
  const [expandedInsights, setExpandedInsights] = useState<Set<string>>(new Set());
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

  const toggleInsightExpansion = (insightId: string) => {
    setExpandedInsights((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(insightId)) {
        newSet.delete(insightId);
      } else {
        newSet.add(insightId);
      }
      return newSet;
    });
  };

  return (
    <motion.div
      className={cn(
        'relative overflow-hidden rounded-2xl border border-amber-200/20',
        'bg-gradient-to-br from-white/70 via-amber-50/50 to-white/70 backdrop-blur-xl',
        'shadow-lg hover:shadow-2xl transition-all duration-500',
        className
      )}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Animated background patterns */}
      <div className="absolute inset-0 opacity-30">
        <svg className="absolute inset-0 w-full h-full" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="insights-pattern" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
              <circle cx="2" cy="2" r="1" fill="#f59e0b" className="opacity-30" />
              <circle cx="22" cy="22" r="1" fill="#f97316" className="opacity-30" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#insights-pattern)" />
        </svg>
      </div>

      {/* Floating orbs */}
      <motion.div
        className="absolute top-10 right-10 w-20 h-20 bg-amber-400/10 rounded-full blur-xl"
        animate={{
          x: [0, 30, 0],
          y: [0, -20, 0],
        }}
        transition={{
          duration: 7,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
      <motion.div
        className="absolute bottom-10 left-10 w-32 h-32 bg-orange-400/10 rounded-full blur-xl"
        animate={{
          x: [0, -20, 0],
          y: [0, 30, 0],
        }}
        transition={{
          duration: 9,
          repeat: Infinity,
          ease: "easeInOut",
          delay: 1,
        }}
      />

      {/* Header */}
      <div className="relative border-b border-amber-200/20">
        <motion.div
          className="relative flex items-center justify-between p-6"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
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
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 shadow-lg shadow-amber-500/25 border border-amber-500/30">
                <motion.div
                  animate={{
                    rotate: [0, 360],
                  }}
                  transition={{
                    duration: 10,
                    repeat: Infinity,
                    ease: "linear",
                    repeatDelay: 2,
                  }}
                >
                  <Brain className="h-7 w-7 text-white" />
                </motion.div>
              </div>
              <AnimatePresence>
                {!isIdle && (
                  <motion.div
                    className="absolute -bottom-1 -right-1 flex items-center justify-center w-5 h-5 rounded-full border-2 border-white bg-gradient-to-r from-amber-400 to-orange-500"
                    initial={{ scale: 0 }}
                    animate={{ scale: [1, 1.3, 1] }}
                    exit={{ scale: 0 }}
                    transition={{ duration: 1, repeat: Infinity }}
                  >
                    <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
            <div>
              <motion.h3
                className="text-xl font-bold bg-gradient-to-r from-amber-700 to-orange-600 bg-clip-text text-transparent flex items-center gap-3"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2 }}
              >
                AI Insights
                <AnimatePresence>
                  {!isIdle && (
                    <motion.span
                      className="text-sm font-normal text-amber-600 flex items-center gap-2 bg-amber-100/50 px-2 py-1 rounded-full"
                      initial={{ opacity: 0, x: 10 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 10 }}
                    >
                      <motion.div
                        className="w-2 h-2 bg-amber-500 rounded-full"
                        animate={{
                          scale: [1, 1.5, 1],
                          opacity: [1, 0.5, 1],
                        }}
                        transition={{ duration: 2, repeat: Infinity }}
                      />
                      Processing
                    </motion.span>
                  )}
                </AnimatePresence>
              </motion.h3>
              <motion.p
                className="text-sm text-gray-600 flex items-center gap-2 mt-1"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
              >
                <Zap className="h-3 w-3 text-amber-500" />
                Intelligent document analysis
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
              className="text-xs bg-white/50 backdrop-blur-sm hover:bg-white/70 border border-amber-200/30 rounded-xl px-4 h-8"
            >
              <motion.div
                animate={{ rotate: isExpanded ? 180 : 0 }}
                transition={{ duration: 0.3 }}
              >
                <ChevronDown className="h-4 w-4" />
              </motion.div>
              {isExpanded ? 'Collapse' : 'Expand'}
            </Button>
          </motion.div>
        </motion.div>
      </div>

      {/* Insights List with Enhanced Cards */}
      <div className="divide-y divide-amber-200/10">
        {sampleInsights.map((insight, index) => {
          const config = insightConfig[insight.type];
          const Icon = config.icon;
          const isExpanded = expandedInsights.has(insight.id);

          return (
            <motion.div
              key={insight.id}
              className="relative group"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 + index * 0.1 }}
              onHoverStart={() => setHoveredInsight(insight.id)}
              onHoverEnd={() => setHoveredInsight(null)}
            >
              <div className="p-6">
                <div className="flex items-start gap-4">
                  <motion.div
                    className={cn(
                      'relative flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border',
                      config.bgColor,
                      config.borderColor,
                      'overflow-hidden'
                    )}
                    whileHover={{
                      scale: 1.1,
                      rotate: 5,
                    }}
                    transition={{ duration: 0.3 }}
                  >
                    {/* Animated progress ring */}
                    <svg className="absolute inset-0 w-full h-full">
                      <motion.circle
                        cx="24"
                        cy="24"
                        r="20"
                        stroke="currentColor"
                        strokeWidth="2"
                        fill="none"
                        className="text-gray-200"
                      />
                      <motion.circle
                        cx="24"
                        cy="24"
                        r="20"
                        stroke="url(#gradient)"
                        strokeWidth="2"
                        fill="none"
                        strokeLinecap="round"
                        initial={{ pathLength: 0 }}
                        animate={{ pathLength: (insight.metadata?.confidence || 0) / 100 }}
                        transition={{ duration: 1, delay: 0.5 + index * 0.1 }}
                        style={{
                          transform: "rotate(-90deg)",
                          transformOrigin: "center",
                        }}
                      />
                      <defs>
                        <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                          <stop offset="0%" stopColor="#f59e0b" />
                          <stop offset="100%" stopColor="#f97316" />
                        </linearGradient>
                      </defs>
                    </svg>
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
                      <Icon className={cn('h-6 w-6 relative z-10', config.color)} />
                    </motion.div>
                  </motion.div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <motion.p
                            className="text-base font-semibold text-gray-800"
                            animate={{
                              color: hoveredInsight === insight.id ? '#f59e0b' : '#1f2937',
                            }}
                          >
                            {insight.title}
                          </motion.p>
                          {insight.metadata?.confidence && (
                            <motion.div
                              className="flex items-center gap-1 text-xs text-amber-600 bg-amber-100/50 px-2 py-1 rounded-full"
                              initial={{ opacity: 0, scale: 0.8 }}
                              animate={{ opacity: 1, scale: 1 }}
                              transition={{ delay: 0.6 + index * 0.1 }}
                            >
                              <Target className="h-3 w-3" />
                              {insight.metadata.confidence}% match
                            </motion.div>
                          )}
                        </div>
                        <p className="text-sm text-gray-600 leading-relaxed">
                          {insight.description}
                        </p>

                        {/* Metadata and tags */}
                        {insight.metadata && (
                          <motion.div
                            className="mt-3 space-y-2"
                            initial={{ opacity: 0, height: 0 }}
                            animate={{
                              opacity: isExpanded ? 1 : 0,
                              height: isExpanded ? 'auto' : 0,
                            }}
                            transition={{ duration: 0.3 }}
                          >
                            <div className="flex items-center gap-4 text-xs text-gray-500">
                              <span className="flex items-center gap-1">
                                <Timer className="h-3 w-3" />
                                {insight.metadata.timestamp}
                              </span>
                            </div>
                            {insight.metadata.tags && (
                              <div className="flex flex-wrap gap-1">
                                {insight.metadata.tags.map((tag, tagIndex) => (
                                  <span
                                    key={tagIndex}
                                    className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-md"
                                  >
                                    <Hash className="h-2 w-2" />
                                    {tag}
                                  </span>
                                ))}
                              </div>
                            )}
                          </motion.div>
                        )}
                      </div>

                      <div className="flex items-center gap-2 ml-4">
                        {/* Expand/collapse button */}
                        <motion.button
                          onClick={() => toggleInsightExpansion(insight.id)}
                          className="p-1.5 rounded-lg hover:bg-gray-100/50 transition-colors"
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.9 }}
                        >
                          <motion.div
                            animate={{ rotate: isExpanded ? 180 : 0 }}
                            transition={{ duration: 0.3 }}
                          >
                            <Plus className="h-4 w-4 text-gray-400" />
                          </motion.div>
                        </motion.button>

                        {/* Action button */}
                        <motion.button
                          onClick={() => handleQuickQuestion(`Tell me more about: ${insight.title}`)}
                          className="p-1.5 rounded-lg bg-amber-100 text-amber-600 hover:bg-amber-200 transition-colors"
                          initial={{ opacity: 0, x: 10 }}
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.9 }}
                        >
                          <ArrowRight className="h-4 w-4" />
                        </motion.button>
                      </div>
                    </div>
                  </div>
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

      {/* Enhanced Quick Input */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            className="border-t border-amber-200/20 bg-gradient-to-br from-amber-50/30 to-orange-50/20 backdrop-blur-sm"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
          >
            <div className="p-6">
              <motion.form
                onSubmit={handleSubmit}
                className="relative"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
              >
                <div className="relative">
                  <motion.input
                    type="text"
                    value={localInput}
                    onChange={(e) => setLocalInput(e.target.value)}
                    placeholder="Ask AI anything about your documents..."
                    className={cn(
                      'w-full rounded-2xl border border-amber-200/30 bg-white/70 backdrop-blur-sm px-5 py-4 pr-14 text-base',
                      'placeholder:text-gray-400',
                      'focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500/50',
                      'transition-all duration-300'
                    )}
                    disabled={isPending}
                    whileFocus={{
                      scale: 1.01,
                      boxShadow: "0 0 0 3px rgba(251, 146, 60, 0.1)",
                    }}
                  />

                  {/* Animated background particles */}
                  <AnimatePresence>
                    {localInput && (
                      <div className="absolute inset-0 overflow-hidden rounded-2xl pointer-events-none">
                        {[...Array(5)].map((_, i) => (
                          <motion.div
                            key={i}
                            className="absolute w-1 h-1 bg-gradient-to-r from-amber-400 to-orange-400 rounded-full"
                            animate={{
                              x: [0, Math.random() * 100 - 50],
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

                  {/* Submit button */}
                  <motion.div
                    className="absolute right-2 top-1/2 -translate-y-1/2"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <Button
                      type="submit"
                      size="sm"
                      disabled={isPending || !localInput.trim()}
                      className="bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white border-0 shadow-lg shadow-amber-500/25 rounded-xl p-3 h-10 w-10"
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
                </div>
              </motion.form>

              {/* Quick action buttons */}
              <motion.div
                className="grid grid-cols-3 gap-3 mt-4"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
              >
                {[
                  {
                    text: '📄 Summarize',
                    question: 'Summarize my recent documents',
                    gradient: 'from-blue-500/10 to-indigo-500/10',
                    icon: <FileText className="h-3 w-3" />
                  },
                  {
                    text: '💡 Insights',
                    question: 'What insights can you find?',
                    gradient: 'from-amber-500/10 to-orange-500/10',
                    icon: <Lightbulb className="h-3 w-3" />
                  },
                  {
                    text: '🔗 Related',
                    question: 'Suggest related topics',
                    gradient: 'from-emerald-500/10 to-teal-500/10',
                    icon: <Target className="h-3 w-3" />
                  },
                ].map((item, index) => (
                  <motion.button
                    key={item.text}
                    type="button"
                    onClick={() => handleQuickQuestion(item.question)}
                    className={cn(
                      'relative p-3 rounded-xl text-xs font-medium text-gray-700',
                      'bg-gradient-to-br',
                      item.gradient,
                      'hover:shadow-md transition-all duration-200',
                      'flex items-center justify-center gap-2'
                    )}
                    whileHover={{ scale: 1.05, y: -2 }}
                    whileTap={{ scale: 0.95 }}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 + index * 0.1 }}
                  >
                    {item.icon}
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