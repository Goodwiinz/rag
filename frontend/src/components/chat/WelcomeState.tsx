'use client';

import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { Activity, Cpu, Satellite, Shield, Zap } from 'lucide-react';
import React from 'react';

export interface WelcomeStateProps {
  onPromptSelect: (prompt: string) => void;
  selectedModel?: string;
}

export function WelcomeState({
  onPromptSelect: _onPromptSelect,
  selectedModel,
}: WelcomeStateProps) {
  // Mouse tracking for parallax effect
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    x.set(e.clientX - centerX);
    y.set(e.clientY - centerY);
  };

  const handleMouseLeave = () => {
    x.set(0);
    y.set(0);
  };

  // Smooth spring physics for the tilt
  const springConfig = { damping: 25, stiffness: 150 };
  const rotateX = useSpring(
    useTransform(y, [-100, 100], [10, -10]),
    springConfig
  );
  const rotateY = useSpring(
    useTransform(x, [-100, 100], [-10, 10]),
    springConfig
  );

  return (
    <div
      className="flex-1 flex flex-col items-center justify-center p-8 perspective-1000"
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.8 }}
        style={{ rotateX, rotateY, transformStyle: 'preserve-3d' }}
        className="text-center max-w-2xl relative"
      >
        {/* Orbital decoration */}
        <div className="relative mb-12 flex items-center justify-center h-64 w-64 mx-auto transform-gpu">
          {/* Outer Ring - Counter Rotate */}
          <motion.div
            style={{ translateZ: 20 }}
            className="absolute inset-0 flex items-center justify-center"
          >
            <div className="w-56 h-56 rounded-full border border-[var(--terminal-border)]/50 animate-[spin_30s_linear_infinite_reverse] orbital-ring-reverse" />
          </motion.div>

          {/* Inner Ring - Rotate */}
          <motion.div
            style={{ translateZ: 40 }}
            className="absolute inset-0 flex items-center justify-center"
          >
            <div className="w-32 h-32 rounded-full border border-[var(--terminal-border)] animate-[spin_20s_linear_infinite] orbital-ring" />
          </motion.div>

          {/* Core Container */}
          <motion.div
            style={{ translateZ: 60 }}
            className="relative w-24 h-24 flex items-center justify-center"
          >
            {/* Satellite Icon with Float */}
            <Satellite className="w-12 h-12 text-[var(--phosphor-green)] float-gentle drop-shadow-[0_0_15px_rgba(212,160,57,0.3)]" />

            {/* Scanning Beam Effect */}
            <motion.div
              animate={{ top: ['0%', '100%', '0%'], opacity: [0, 1, 0] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
              className="absolute left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-sol to-transparent w-full"
            />
          </motion.div>

          {/* Radar Pings - Background */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div
              className="w-full h-full rounded-full border border-sol/5 animate-ping"
              style={{ animationDuration: '3s' }}
            />
          </div>
        </div>

        <motion.div style={{ translateZ: 30 }}>
          <h2
            className="text-xl text-[var(--terminal-text)] tracking-wider mb-2"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {selectedModel
              ? 'NEURAL LINK ESTABLISHED'
              : 'AWAITING NEURAL CORE SELECTION'}
          </h2>
          <p
            className="text-sm text-[var(--terminal-text-muted)] text-center max-w-md mx-auto"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {selectedModel
              ? 'Ready to receive transmissions. Enter your query below.'
              : 'Select a neural core from the command bar to initialize the interface.'}
          </p>
        </motion.div>

        {selectedModel && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            style={{ translateZ: 20 }}
            className="mt-8 grid grid-cols-2 gap-4 max-w-lg mx-auto"
          >
            {[
              {
                icon: Zap,
                label: 'RAPID PROCESSING',
                desc: 'Sub-second response latency',
              },
              {
                icon: Shield,
                label: 'LOCAL ONLY',
                desc: 'All data stays on device',
              },
              {
                icon: Cpu,
                label: 'NEURAL INFERENCE',
                desc: 'Advanced language model',
              },
              {
                icon: Activity,
                label: 'REAL-TIME STREAM',
                desc: 'Live response generation',
              },
            ].map((item, idx) => (
              <div
                key={idx}
                className="p-4 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)]/50 text-left hover:border-[var(--phosphor-green)]/20 transition-all group backdrop-blur-sm"
              >
                <item.icon className="w-5 h-5 text-[var(--phosphor-green)] mb-2 group-hover:scale-110 transition-transform" />
                <h3
                  className="text-xs text-[var(--terminal-text)] mb-1"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  {item.label}
                </h3>
                <p
                  className="text-[10px] text-[var(--terminal-text-muted)]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  {item.desc}
                </p>
              </div>
            ))}
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}

export default WelcomeState;
