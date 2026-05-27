'use client';

import { motion } from 'framer-motion';
import { Cpu, GitBranch, Shield, Wifi, Zap } from 'lucide-react';
import React from 'react';

export interface WelcomeStateProps {
  onPromptSelect: (prompt: string) => void;
  selectedModel?: string;
}

const FEATURES = [
  {
    icon: Zap,
    label: 'RAPID PROCESSING',
    desc: 'Sub-second response latency',
    seed: 'Summarize the current document in three bullets — ',
  },
  {
    icon: GitBranch,
    label: 'CITATION CHAIN',
    desc: 'Inline references to source passages',
    seed: 'Walk me through the citations supporting ',
  },
  {
    icon: Cpu,
    label: 'NEURAL INFERENCE',
    desc: 'Multi-step agent with tool access',
    seed: 'Plan a research workflow for ',
  },
  {
    icon: Shield,
    label: 'LOCAL CONTEXT',
    desc: 'Grounded in your knowledge graph',
    seed: 'Explain how the entities in my graph relate to ',
  },
] as const;

const NOUS_EASE: [number, number, number, number] = [0.16, 1, 0.3, 1];

export function WelcomeState({
  onPromptSelect,
  selectedModel,
}: WelcomeStateProps) {
  const ready = Boolean(selectedModel);

  return (
    <div
      className="relative flex-1 flex flex-col items-center justify-center p-8 sm:p-16 overflow-hidden"
      style={{ background: 'var(--term-bg)' }}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-30"
        style={{
          backgroundImage:
            'radial-gradient(1px 1px at 18% 28%, var(--term-accent) 0%, transparent 100%), radial-gradient(1px 1px at 72% 20%, var(--term-accent) 0%, transparent 100%), radial-gradient(1.5px 1.5px at 38% 76%, var(--term-accent) 0%, transparent 100%), radial-gradient(1px 1px at 86% 62%, var(--term-accent) 0%, transparent 100%), radial-gradient(1px 1px at 12% 86%, var(--term-accent) 0%, transparent 100%), radial-gradient(1px 1px at 56% 14%, var(--term-accent) 0%, transparent 100%)',
        }}
      />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: NOUS_EASE }}
        className="relative z-10 flex flex-col items-center max-w-2xl w-full"
      >
        <div className="relative w-52 h-52 sm:w-64 sm:h-64 grid place-items-center mb-10 sm:mb-12">
          <div
            className="absolute inset-0 rounded-full"
            style={{
              border: '1px solid rgba(48, 54, 61, 0.5)',
              animation: 'term-spin 30s linear infinite reverse',
            }}
          />
          <div
            className="absolute rounded-full"
            style={{
              inset: '40px',
              border: '1px solid var(--term-border)',
              animation: 'term-spin 20s linear infinite',
            }}
          />
          <div
            aria-hidden
            className="absolute inset-0 rounded-full"
            style={{
              border: '1px solid rgba(212, 160, 57, 0.08)',
              animation: 'term-radar 3s ease-in-out infinite',
            }}
          />
          <div
            className="relative w-20 h-20 grid place-items-center"
            style={{
              color: 'var(--term-accent)',
              filter: 'drop-shadow(0 0 15px rgba(212, 160, 57, 0.4))',
              animation: 'term-float 4s ease-in-out infinite',
            }}
          >
            <Wifi className="w-14 h-14" strokeWidth={1.4} />
          </div>
        </div>

        <h2
          className="font-nous-mono text-lg sm:text-xl font-medium mb-2 text-center"
          style={{
            color: 'var(--term-text)',
            letterSpacing: '0.18em',
          }}
        >
          {ready ? 'NEURAL LINK ESTABLISHED' : 'AWAITING NEURAL HANDSHAKE'}
        </h2>
        <p
          className="font-nous-mono text-xs mb-10 sm:mb-12 max-w-md text-center"
          style={{ color: 'var(--term-text-muted)' }}
        >
          {ready
            ? 'AWAITING TRANSMISSION · INPUT QUERY VIA STREAM'
            : 'SELECT MODEL FROM TOOLBAR · OPEN STREAM TO PROCEED'}
        </p>

        {ready && (
          <motion.div
            initial="hidden"
            animate="visible"
            variants={{
              hidden: {},
              visible: {
                transition: { staggerChildren: 0.07, delayChildren: 0.35 },
              },
            }}
            className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl"
          >
            {FEATURES.map((feat, idx) => {
              const Icon = feat.icon;
              return (
                <motion.button
                  key={feat.label}
                  variants={{
                    hidden: { opacity: 0, y: 12 },
                    visible: {
                      opacity: 1,
                      y: 0,
                      transition: { duration: 0.45, ease: NOUS_EASE },
                    },
                  }}
                  onClick={() => onPromptSelect(feat.seed)}
                  className="group text-left rounded-[10px] p-3.5 transition-colors duration-200"
                  style={{
                    background: 'rgba(13, 13, 18, 0.5)',
                    border: '1px solid var(--term-border)',
                    backdropFilter: 'blur(8px)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor =
                      'rgba(212, 160, 57, 0.3)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--term-border)';
                  }}
                >
                  <div className="flex items-start justify-between mb-2">
                    <Icon
                      className="w-4 h-4"
                      style={{ color: 'var(--term-accent)' }}
                      strokeWidth={1.6}
                    />
                    <span
                      className="font-nous-mono text-[9px] tabular-nums"
                      style={{ color: 'var(--term-text-dim)' }}
                    >
                      0{idx + 1}
                    </span>
                  </div>
                  <div
                    className="font-nous-mono text-[10px] mb-1"
                    style={{
                      color: 'var(--term-text)',
                      letterSpacing: '0.06em',
                    }}
                  >
                    {feat.label}
                  </div>
                  <div
                    className="font-nous-mono text-[9px] leading-relaxed"
                    style={{ color: 'var(--term-text-muted)' }}
                  >
                    {feat.desc}
                  </div>
                </motion.button>
              );
            })}
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}

export default WelcomeState;
