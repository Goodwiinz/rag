'use client';

import { motion } from 'framer-motion';
import { Radio } from 'lucide-react';

export interface ModelLoadingProgressProps {
  progress: string;
  progressVal: number;
}

export function ModelLoadingProgress({
  progress,
  progressVal,
}: ModelLoadingProgressProps) {
  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      className="border-b border-[var(--nous-border-1)] overflow-hidden bg-[var(--nous-bg-1)]"
    >
      <div className="px-4 py-3 max-w-4xl mx-auto">
        <div className="flex items-center gap-4">
          <div className="relative">
            <Radio className="w-5 h-5 text-[var(--nous-sol)] animate-pulse" />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-2 h-2 rounded-full bg-[var(--nous-sol)] animate-ping" />
            </div>
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1">
              <span
                className="text-xs text-[var(--nous-sol)]"
                style={{ fontFamily: 'var(--nous-font-mono)' }}
              >
                ESTABLISHING NEURAL LINK...
              </span>
              <span
                className="text-xs text-[var(--nous-fg-3)]"
                style={{ fontFamily: 'var(--nous-font-mono)' }}
              >
                {Math.round(progressVal * 100)}%
              </span>
            </div>
            <div className="h-1 bg-[var(--nous-border-1)] rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-[var(--nous-sol)] to-[var(--nous-helios)]"
                initial={{ width: 0 }}
                animate={{ width: progressVal * 100 + '%' }}
                transition={{ duration: 0.3 }}
              />
            </div>
            <p
              className="text-[10px] text-[var(--nous-fg-3)] mt-1 truncate"
              style={{ fontFamily: 'var(--nous-font-mono)' }}
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
