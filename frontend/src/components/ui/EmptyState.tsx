'use client';

import { type LucideIcon } from 'lucide-react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

interface EmptyStateAction {
  label: string;
  href?: string;
  onClick?: () => void;
  variant?: 'default' | 'outline' | 'ghost';
}

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: EmptyStateAction;
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={cn(
        'flex flex-col items-center justify-center py-16 text-center',
        className
      )}
    >
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.3 }}
        className="flex items-center justify-center w-12 h-12 rounded-lg bg-primary/10 border border-primary/20 mb-4"
      >
        <Icon className="w-5 h-5 text-primary" />
      </motion.div>
      <motion.h3
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15, duration: 0.3 }}
        className="text-sm font-mono font-semibold text-[var(--terminal-text)] tracking-wider mb-1.5"
      >
        {title}
      </motion.h3>
      <motion.p
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.3 }}
        className="text-xs font-mono text-muted-foreground max-w-xs leading-relaxed"
      >
        {description}
      </motion.p>
      {action && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25, duration: 0.3 }}
          className="mt-5"
        >
          {action.href ? (
            <Link href={action.href}>
              <Button
                variant={action.variant || 'outline'}
                size="sm"
                className="font-mono text-xs tracking-wider"
              >
                {action.label}
              </Button>
            </Link>
          ) : (
            <Button
              variant={action.variant || 'outline'}
              size="sm"
              onClick={action.onClick}
              className="font-mono text-xs tracking-wider"
            >
              {action.label}
            </Button>
          )}
        </motion.div>
      )}
    </motion.div>
  );
}
