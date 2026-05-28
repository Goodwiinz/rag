'use client';

import { getAnalytics } from '@/lib/analytics';
import { cn } from '@/lib/utils';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowRight,
  MessageSquare,
  Search,
  Sparkles,
  Target,
  Upload,
  Zap,
} from 'lucide-react';
import Link from 'next/link';
import React, { useState } from 'react';

interface QuickAction {
  title: string;
  description: string;
  href: string;
  icon: React.ElementType;
  color: string;
  bgGradient: string;
  glowColor: string;
}

const quickActions: QuickAction[] = [
  {
    title: 'Upload Documents',
    description: 'Add files to your knowledge base',
    href: '/documents/upload',
    icon: Upload,
    color: 'text-emerald-500',
    bgGradient:
      'from-emerald-500/10 to-teal-500/10 hover:from-emerald-500/20 hover:to-teal-500/20',
    glowColor: 'emerald',
  },
  {
    title: 'Semantic Search',
    description: 'Find information across documents',
    href: '/search',
    icon: Search,
    color: 'text-blue-500',
    bgGradient:
      'from-blue-500/10 to-indigo-500/10 hover:from-blue-500/20 hover:to-indigo-500/20',
    glowColor: 'blue',
  },
  {
    title: 'AI Chat',
    description: 'Chat with your AI assistant',
    href: '/chat',
    icon: MessageSquare,
    color: 'text-amber-500',
    bgGradient:
      'from-amber-500/10 to-orange-500/10 hover:from-amber-500/20 hover:to-orange-500/20',
    glowColor: 'amber',
  },
];

interface QuickActionsGridProps {
  className?: string;
}

export function QuickActionsGrid({ className }: QuickActionsGridProps) {
  const [hoveredAction, setHoveredAction] = useState<string | null>(null);

  const handleActionClick = (actionTitle: string, actionHref: string) => {
    try {
      const analytics = getAnalytics();
      analytics.trackUserInteraction('quick_action', 'click', {
        action: actionTitle,
        destination: actionHref,
      });
      analytics.trackFeatureUsage(
        'quick_actions',
        actionTitle.toLowerCase().replace(' ', '_')
      );
    } catch (error) {
      // Analytics not initialized, silently ignore
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
    hidden: { opacity: 0, scale: 0.9, y: 20 },
    visible: {
      opacity: 1,
      scale: 1,
      y: 0,
      transition: {
        type: 'spring' as const,
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
      {/* Animated background effects */}
      <div className="absolute inset-0 pointer-events-none">
        <motion.div
          className="absolute top-0 right-0 w-32 h-32 rounded-full bg-gradient-to-br from-amber-400/10 to-orange-400/10"
          animate={{
            scale: [1, 1.2, 1],
            rotate: [0, 180, 360],
          }}
          transition={{
            duration: 10,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
        <motion.div
          className="absolute bottom-0 left-0 w-24 h-24 rounded-full bg-gradient-to-tr from-purple-400/10 to-pink-400/10"
          animate={{
            scale: [1, 1.3, 1],
            rotate: [360, 0, -360],
          }}
          transition={{
            duration: 15,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: 2,
          }}
        />
      </div>

      {/* Glass reflection effect */}
      <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent opacity-0 hover:opacity-100 transition-opacity duration-700" />

      {/* Header */}
      <motion.div
        className="relative border-b border-border/50 p-6"
        variants={itemVariants}
      >
        <div className="flex items-center gap-4">
          <motion.div
            className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-amber-500/30"
            whileHover={{
              scale: 1.1,
              rotate: [0, -5, 5, 0],
            }}
            transition={{ duration: 0.3 }}
          >
            <motion.div
              animate={{
                rotate: [0, 360],
              }}
              transition={{
                duration: 20,
                repeat: Infinity,
                ease: 'linear',
                repeatDelay: 5,
              }}
            >
              <Sparkles className="h-6 w-6 text-amber-500" />
            </motion.div>
          </motion.div>
          <div>
            <motion.h3
              className="text-lg font-semibold text-foreground flex items-center gap-2"
              variants={itemVariants}
            >
              <span className="text-[var(--nous-fg-accent-safe)]">
                Quick Actions
              </span>
              <Target className="h-4 w-4 text-amber-500" />
            </motion.h3>
            <motion.p
              className="text-sm text-muted-foreground flex items-center gap-1"
              variants={itemVariants}
            >
              <Zap className="h-3 w-3 text-amber-500" />
              Jump to common tasks
            </motion.p>
          </div>
        </div>
      </motion.div>

      {/* Actions Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-6">
        {quickActions.map((action, index) => (
          <motion.div
            key={action.title}
            variants={itemVariants}
            onHoverStart={() => setHoveredAction(action.title)}
            onHoverEnd={() => setHoveredAction(null)}
          >
            <Link
              href={action.href}
              onClick={() => handleActionClick(action.title, action.href)}
              className="group relative block"
            >
              <motion.div
                className={cn(
                  'relative overflow-hidden rounded-2xl border border-border/30',
                  'bg-gradient-to-br transition-all duration-500',
                  action.bgGradient,
                  'hover:border-amber-500/40',
                  'p-6'
                )}
                whileHover={{
                  scale: 1.02,
                  y: -2,
                  boxShadow:
                    '0 20px 25px -5px rgba(251,191,36,0.1), 0 10px 10px -5px rgba(251,191,36,0.04)',
                }}
                whileTap={{ scale: 0.98 }}
              >
                {/* Hover glow effect */}
                <motion.div
                  className="absolute inset-0 bg-gradient-to-br opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
                  style={{
                    background: `radial-gradient(circle at center, ${action.glowColor === 'amber' ? 'rgba(251,191,36,0.1)' : action.glowColor === 'blue' ? 'rgba(59,130,246,0.1)' : action.glowColor === 'emerald' ? 'rgba(16,185,129,0.1)' : 'rgba(147,51,234,0.1)'} 0%, transparent 70%)`,
                  }}
                />

                {/* Floating particles */}
                <AnimatePresence>
                  {hoveredAction === action.title && (
                    <div className="absolute inset-0 overflow-hidden rounded-2xl pointer-events-none">
                      {[...Array(5)].map((_, i) => (
                        <motion.div
                          key={i}
                          className="absolute w-1 h-1 rounded-full"
                          style={{
                            backgroundColor:
                              action.glowColor === 'amber'
                                ? '#f59e0b'
                                : action.glowColor === 'blue'
                                  ? '#3b82f6'
                                  : action.glowColor === 'emerald'
                                    ? '#10b981'
                                    : '#9333ea',
                            left: `${Math.random() * 80 + 10}%`,
                            top: `${Math.random() * 80 + 10}%`,
                          }}
                          animate={{
                            y: [0, -30, 0],
                            x: [0, Math.random() * 20 - 10, 0],
                            opacity: [0, 1, 0],
                          }}
                          transition={{
                            duration: 2 + Math.random(),
                            repeat: Infinity,
                            delay: Math.random() * 0.5,
                          }}
                        />
                      ))}
                    </div>
                  )}
                </AnimatePresence>

                <div className="relative flex items-start gap-4">
                  <motion.div
                    className={cn(
                      'flex h-12 w-12 shrink-0 items-center justify-center rounded-xl',
                      'bg-card/50 backdrop-blur-sm border border-border/50'
                    )}
                    whileHover={{
                      scale: 1.1,
                      rotate: [0, -5, 5, 0],
                    }}
                    transition={{ duration: 0.3 }}
                  >
                    <motion.div
                      animate={{
                        rotate: hoveredAction === action.title ? [0, 360] : 0,
                      }}
                      transition={{
                        duration: hoveredAction === action.title ? 0.6 : 0,
                        ease: 'easeInOut',
                      }}
                    >
                      <action.icon className={cn('h-6 w-6', action.color)} />
                    </motion.div>
                  </motion.div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <motion.h4
                        className={cn(
                          'text-sm font-semibold text-foreground transition-colors duration-300',
                          hoveredAction === action.title ? 'text-amber-600' : ''
                        )}
                      >
                        {action.title}
                      </motion.h4>
                      <motion.div
                        className="flex items-center gap-1"
                        initial={{ opacity: 0, x: -10 }}
                        animate={{
                          opacity: hoveredAction === action.title ? 1 : 0,
                          x: hoveredAction === action.title ? 0 : -10,
                        }}
                        transition={{ duration: 0.2 }}
                      >
                        <ArrowRight
                          className={cn(
                            'h-4 w-4 transition-colors duration-300',
                            hoveredAction === action.title
                              ? 'text-amber-500'
                              : 'text-muted-foreground'
                          )}
                        />
                      </motion.div>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {action.description}
                    </p>
                  </div>
                </div>

                {/* Shine effect on hover */}
                <motion.div
                  className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -skew-x-12"
                  initial={{ x: '-100%' }}
                  whileHover={{ x: '200%' }}
                  transition={{ duration: 0.6, ease: 'easeInOut' }}
                />
              </motion.div>
            </Link>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
