'use client';

import { motion } from 'framer-motion';
import { ArrowRight, BookOpen, Code2, Search, Sparkles } from 'lucide-react';
import React from 'react';

export interface WelcomeStateProps {
  onPromptSelect: (prompt: string) => void;
  selectedModel?: string;
}

const SUGGESTED_PROMPTS = [
  {
    icon: Search,
    label: 'Research a topic',
    prompt: 'Help me research ',
  },
  {
    icon: BookOpen,
    label: 'Summarize a document',
    prompt: 'Summarize the key points of ',
  },
  {
    icon: Code2,
    label: 'Explain code',
    prompt: 'Explain how this code works: ',
  },
  {
    icon: Sparkles,
    label: 'Generate ideas',
    prompt: 'Help me brainstorm ideas for ',
  },
];

export function WelcomeState({
  onPromptSelect,
  selectedModel,
}: WelcomeStateProps) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-4 sm:p-8">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="text-center max-w-lg w-full"
      >
        {/* Brand mark */}
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.1, duration: 0.5 }}
          className="mb-6 sm:mb-10 flex items-center justify-center"
        >
          <div className="relative w-16 h-16 sm:w-20 sm:h-20 flex items-center justify-center">
            <div className="absolute inset-0 rounded-full bg-[var(--nous-sol)]/10 animate-pulse" style={{ animationDuration: '3s' }} />
            <div className="absolute inset-2 rounded-full bg-[var(--nous-sol)]/5" />
            <span
              className="text-2xl sm:text-3xl font-semibold text-[var(--nous-sol)]"
              style={{ fontFamily: 'var(--nous-font-heading)' }}
            >
              N
            </span>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.5 }}
        >
          <h2
            className="text-xl sm:text-2xl font-medium text-[var(--nous-fg-1)] mb-2"
            style={{ fontFamily: 'var(--nous-font-heading)' }}
          >
            {selectedModel ? 'How can I help?' : 'Select a model to begin'}
          </h2>
          <p
            className="text-sm sm:text-base text-[var(--nous-fg-3)] max-w-sm mx-auto"
            style={{ fontFamily: 'var(--nous-font-body)', lineHeight: '1.6' }}
          >
            {selectedModel
              ? 'Ask anything — I can research, summarize, and reason across your documents.'
              : 'Choose a model from the toolbar above to start a conversation.'}
          </p>
        </motion.div>

        {selectedModel && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.5 }}
            className="mt-6 sm:mt-10 grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3"
          >
            {SUGGESTED_PROMPTS.map((item, idx) => (
              <button
                key={idx}
                onClick={() => onPromptSelect(item.prompt)}
                className="group flex items-center gap-3 p-3.5 sm:p-4 rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]/50 text-left transition-all duration-200 hover:border-[var(--nous-sol)]/30 hover:bg-[var(--nous-sol)]/5 active:scale-[0.98]"
              >
                <item.icon className="w-4 h-4 text-[var(--nous-fg-3)] group-hover:text-[var(--nous-sol)] transition-colors shrink-0" />
                <span
                  className="text-[13px] sm:text-sm text-[var(--nous-fg-2)] group-hover:text-[var(--nous-fg-1)] transition-colors flex-1"
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
                >
                  {item.label}
                </span>
                <ArrowRight className="w-3.5 h-3.5 text-[var(--nous-fg-3)]/0 group-hover:text-[var(--nous-sol)] transition-all translate-x-0 group-hover:translate-x-0.5" />
              </button>
            ))}
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}

export default WelcomeState;
