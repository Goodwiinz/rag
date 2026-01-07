'use client';

import { motion } from 'framer-motion';
import { Activity, BookOpen, Cpu, FileText, Shield, Sparkles, Zap } from 'lucide-react';

// ============================================
// TYPES
// ============================================

interface StarterPrompt {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  prompt: string;
}

export interface WelcomeStateProps {
  onPromptSelect: (prompt: string) => void;
  selectedModel?: string;
  starterPrompts?: StarterPrompt[];
}

// ============================================
// DEFAULT PROMPTS
// ============================================

const DEFAULT_STARTER_PROMPTS: StarterPrompt[] = [
  {
    icon: BookOpen,
    title: 'Summarize Research',
    prompt: 'Summarize the key findings from the recent papers on RAG optimization',
  },
  {
    icon: Zap,
    title: 'Compare Embeddings',
    prompt: 'Compare BAAI/bge-large vs OpenAI embeddings for semantic search',
  },
  {
    icon: FileText,
    title: 'Analyze Document',
    prompt: 'Analyze the methodology section of the uploaded paper',
  },
  {
    icon: Sparkles,
    title: 'Generate Ideas',
    prompt: 'Suggest improvements for our current retrieval pipeline',
  },
];

// ============================================
// COMPONENT
// ============================================

export function WelcomeState({
  onPromptSelect,
  selectedModel,
  starterPrompts = DEFAULT_STARTER_PROMPTS,
}: WelcomeStateProps) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-center max-w-2xl"
      >
        {/* Logo */}
        <div className="relative w-24 h-24 mx-auto mb-8">
          <div className="absolute inset-0 rounded-full bg-[var(--phosphor-green)]/10 animate-pulse" />
          <div className="absolute inset-2 rounded-full border-2 border-[var(--phosphor-green)]/30 flex items-center justify-center">
            <Sparkles className="w-10 h-10 text-[var(--phosphor-green)]" />
          </div>
        </div>

        {/* Title */}
        <h1
          className="text-2xl text-[var(--phosphor-green)] mb-3"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {selectedModel ? 'NEURAL LINK ESTABLISHED' : 'AWAITING MODEL SELECTION'}
        </h1>
        <p
          className="text-sm text-[var(--terminal-text-muted)] mb-8"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {selectedModel
            ? 'Your GenAI research companion is ready. Ask questions about your documents, explore research papers, and generate insights.'
            : 'Select a neural core from the input bar below to initialize the interface.'}
        </p>

        {/* Starter Prompts */}
        {selectedModel && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {starterPrompts.map((item, idx) => (
                <motion.button
                  key={idx}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 + idx * 0.1 }}
                  onClick={() => onPromptSelect(item.prompt)}
                  className="flex items-start gap-3 p-4 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] hover:border-[var(--phosphor-green)]/30 hover:bg-[var(--terminal-elevated)] text-left transition-all group"
                >
                  <div className="p-2 rounded-lg bg-[var(--phosphor-green)]/10 text-[var(--phosphor-green)] group-hover:bg-[var(--phosphor-green)]/20 transition-colors">
                    <item.icon className="w-4 h-4" />
                  </div>
                  <div>
                    <h3
                      className="text-xs text-[var(--terminal-text)] mb-1"
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}
                    >
                      {item.title}
                    </h3>
                    <p
                      className="text-[10px] text-[var(--terminal-text-muted)] line-clamp-2"
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}
                    >
                      {item.prompt}
                    </p>
                  </div>
                </motion.button>
              ))}
            </div>

            {/* Features */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="mt-8 grid grid-cols-2 sm:grid-cols-4 gap-3"
            >
              {[
                { icon: Zap, label: 'RAPID PROCESSING' },
                { icon: Shield, label: 'SECURE' },
                { icon: Cpu, label: 'RAG ENABLED' },
                { icon: Activity, label: 'REAL-TIME' },
              ].map((item, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 p-2 rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)]"
                >
                  <item.icon className="w-3 h-3 text-[var(--phosphor-green)]" />
                  <span
                    className="text-[10px] text-[var(--terminal-text-muted)]"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    {item.label}
                  </span>
                </div>
              ))}
            </motion.div>
          </>
        )}
      </motion.div>
    </div>
  );
}

export default WelcomeState;
