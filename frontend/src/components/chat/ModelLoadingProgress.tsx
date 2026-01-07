'use client';

import { motion } from 'framer-motion';
import { Radio } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface ModelLoadingProgressProps {
  progress: string;
  progressVal: number;
}

// ============================================
// COMPONENT
// ============================================

export function ModelLoadingProgress({
  progress,
  progressVal,
}: ModelLoadingProgressProps) {
  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      className="border-b border-[var(--terminal-border)] overflow-hidden bg-[var(--terminal-bg)]"
    >
      <div className="px-4 py-3 max-w-4xl mx-auto">
        <div className="flex items-center gap-4">
          <div className="relative">
            <Radio className="w-5 h-5 text-[var(--phosphor-green)] animate-pulse" />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-2 h-2 rounded-full bg-[var(--phosphor-green)] animate-ping" />
            </div>
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1">
              <span
                className="text-xs text-[var(--phosphor-green)]"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                ESTABLISHING NEURAL LINK...
              </span>
              <span
                className="text-xs text-[var(--terminal-text-muted)]"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                {Math.round(progressVal * 100)}%
              </span>
            </div>
            <div className="h-1 bg-[var(--terminal-border)] rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-[var(--phosphor-green)] to-[var(--phosphor-green-dim)]"
                initial={{ width: 0 }}
                animate={{ width: progressVal * 100 + '%' }}
                transition={{ duration: 0.3 }}
              />
            </div>
            <p
              className="text-[10px] text-[var(--terminal-text-muted)] mt-1 truncate"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {progress}
            </p>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export default ModelLoadingProgress;
