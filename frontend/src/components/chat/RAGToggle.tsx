'use client';

import { cn } from '@/lib/utils';
import { Database, Loader2, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useState } from 'react';

export interface RAGToggleProps {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  isLoading?: boolean;
  disabled?: boolean;
  disabledReason?: string;
  compact?: boolean;
}

const LOCAL_STORAGE_KEY = 'rag-enabled-preference';

export function RAGToggle({
  enabled,
  onToggle,
  isLoading = false,
  disabled = false,
  disabledReason,
  compact = false,
}: RAGToggleProps) {
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    const savedPreference = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (savedPreference !== null) {
      const savedEnabled = savedPreference === 'true';
      if (savedEnabled !== enabled) {
        onToggle(savedEnabled);
      }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
        'focus:outline-hidden focus:ring-2 focus:ring-(--nous-sol)/30',
        disabled
          ? 'bg-(--nous-bg-1) border-(--nous-border-1) opacity-50 cursor-not-allowed'
          : enabled
            ? 'bg-(--nous-sol)/10 border-(--nous-sol)/40 hover:border-(--nous-sol)/60'
            : 'bg-(--nous-bg-2) border-(--nous-border-1) hover:border-(--nous-fg-3)'
      )}
      style={{ fontFamily: 'var(--nous-font-mono)' }}
      title={disabled ? disabledReason : enabled ? 'Disable RAG context' : 'Enable RAG context'}
      whileHover={!disabled ? { scale: 1.02 } : undefined}
      whileTap={!disabled ? { scale: 0.98 } : undefined}
    >
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
                  enabled ? 'text-(--nous-sol)' : 'text-(--nous-fg-3)'
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
                  enabled ? 'text-(--nous-sol)' : 'text-(--nous-fg-3)'
                )}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {enabled && !isLoading && (
          <motion.div
            className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-(--nous-sol)"
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

      {!compact && (
        <span
          className={cn(
            'text-xs uppercase tracking-wider transition-colors hidden sm:inline',
            enabled ? 'text-(--nous-sol)' : 'text-(--nous-fg-3)'
          )}
        >
          RAG
        </span>
      )}

      <div
        className={cn(
          'relative w-8 h-4 rounded-full transition-colors duration-300',
          enabled ? 'bg-(--nous-sol)/30' : 'bg-(--nous-border-1)'
        )}
      >
        <motion.div
          className={cn(
            'absolute top-0.5 w-3 h-3 rounded-full transition-colors shadow-xs',
            enabled ? 'bg-(--nous-sol)' : 'bg-(--nous-fg-3)'
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

      <AnimatePresence>
        {isHovered && disabled && disabledReason && (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 5 }}
            className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 rounded-lg bg-(--nous-bg-3) border border-(--nous-border-1) text-[10px] text-(--nous-fg-3) whitespace-nowrap z-50"
          >
            {disabledReason}
            <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-(--nous-border-1)" />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.button>
  );
}

export default RAGToggle;
