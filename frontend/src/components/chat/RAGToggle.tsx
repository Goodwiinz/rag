'use client';

import { cn } from '@/lib/utils';
import { Database, Loader2, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useState } from 'react';

export interface RAGToggleProps {
  /** Whether RAG is enabled */
  enabled: boolean;
  /** Callback when toggle changes */
  onToggle: (enabled: boolean) => void;
  /** Whether RAG retrieval is in progress */
  isLoading?: boolean;
  /** Whether the toggle is disabled (e.g., for cloud models) */
  disabled?: boolean;
  /** Optional tooltip text when disabled */
  disabledReason?: string;
  /** Compact mode for smaller displays */
  compact?: boolean;
}

const LOCAL_STORAGE_KEY = 'rag-enabled-preference';

/**
 * RAG Toggle Component
 *
 * Allows users to enable/disable RAG context retrieval for local models.
 * Styled to match the Terminal Observatory theme.
 */
export function RAGToggle({
  enabled,
  onToggle,
  isLoading = false,
  disabled = false,
  disabledReason,
  compact = false,
}: RAGToggleProps) {
  const [isHovered, setIsHovered] = useState(false);

  // Load preference from localStorage on mount
  useEffect(() => {
    const savedPreference = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (savedPreference !== null) {
      const savedEnabled = savedPreference === 'true';
      if (savedEnabled !== enabled) {
        onToggle(savedEnabled);
      }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Save preference to localStorage when changed
  const handleToggle = () => {
    if (disabled || isLoading) return;
    const newValue = !enabled;
    localStorage.setItem(LOCAL_STORAGE_KEY, String(newValue));
    onToggle(newValue);
  };

  return (
    <motion.button
      onClick={handleToggle}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      disabled={disabled || isLoading}
      className={cn(
        'relative flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all duration-300',
        'focus:outline-none focus:ring-2 focus:ring-[var(--phosphor-green)]/30',
        disabled
          ? 'bg-[var(--terminal-bg)] border-[var(--terminal-border)] opacity-50 cursor-not-allowed'
          : enabled
            ? 'bg-[var(--phosphor-green)]/10 border-[var(--phosphor-green)]/40 hover:border-[var(--phosphor-green)]/60'
            : 'bg-[var(--terminal-surface)] border-[var(--terminal-border)] hover:border-[var(--terminal-text-dim)]'
      )}
      style={{ fontFamily: "'JetBrains Mono', monospace" }}
      title={disabled ? disabledReason : enabled ? 'Disable RAG context' : 'Enable RAG context'}
      aria-label={disabled ? disabledReason : enabled ? 'Disable RAG context' : 'Enable RAG context'}
      whileHover={!disabled ? { scale: 1.02 } : undefined}
      whileTap={!disabled ? { scale: 0.98 } : undefined}
    >
      {/* Icon with loading state */}
      <div className="relative">
        <AnimatePresence mode="wait">
          {isLoading ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0, rotate: -90 }}
              animate={{ opacity: 1, rotate: 0 }}
              exit={{ opacity: 0, rotate: 90 }}
              transition={{ duration: 0.2 }}
            >
              <Loader2
                className={cn(
                  'w-3.5 h-3.5 animate-spin',
                  enabled ? 'text-[var(--phosphor-green)]' : 'text-[var(--terminal-text-dim)]'
                )}
              />
            </motion.div>
          ) : (
            <motion.div
              key="icon"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ duration: 0.2 }}
            >
              <Database
                className={cn(
                  'w-3.5 h-3.5 transition-colors',
                  enabled ? 'text-[var(--phosphor-green)]' : 'text-[var(--terminal-text-dim)]'
                )}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Active indicator pulse */}
        {enabled && !isLoading && (
          <motion.div
            className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-[var(--phosphor-green)]"
            animate={{
              scale: [1, 1.2, 1],
              opacity: [1, 0.7, 1],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          />
        )}
      </div>

      {/* Label */}
      {!compact && (
        <span
          className={cn(
            'text-xs uppercase tracking-wider transition-colors',
            enabled ? 'text-[var(--phosphor-green)]' : 'text-[var(--terminal-text-dim)]'
          )}
        >
          RAG
        </span>
      )}

      {/* Toggle switch */}
      <div
        className={cn(
          'relative w-8 h-4 rounded-full transition-colors duration-300',
          enabled ? 'bg-[var(--phosphor-green)]/30' : 'bg-[var(--terminal-border)]'
        )}
      >
        <motion.div
          className={cn(
            'absolute top-0.5 w-3 h-3 rounded-full transition-colors shadow-sm',
            enabled ? 'bg-[var(--phosphor-green)]' : 'bg-[var(--terminal-text-dim)]'
          )}
          animate={{
            left: enabled ? '16px' : '2px',
          }}
          transition={{
            type: 'spring',
            stiffness: 500,
            damping: 30,
          }}
        />
      </div>

      {/* Hover tooltip for disabled state */}
      <AnimatePresence>
        {isHovered && disabled && disabledReason && (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 5 }}
            className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 rounded bg-[var(--terminal-elevated)] border border-[var(--terminal-border)] text-[10px] text-[var(--terminal-text-muted)] whitespace-nowrap z-50"
          >
            {disabledReason}
            <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-[var(--terminal-border)]" />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.button>
  );
}

export default RAGToggle;
