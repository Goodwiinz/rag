'use client';

import { cn } from '@/lib/utils';
import { AnimatePresence, motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { Bot, Cpu, Lock, Network, Sparkles, Terminal, Wifi, Zap } from 'lucide-react';
import { useEffect, useState } from 'react';

const STEPS = [
  {
    id: 'receive',
    label: 'Parsing natural language query...',
    msg: 'Analyzing intent & entities',
    color: 'text-[var(--phosphor-green)]',
    bg: 'bg-[var(--phosphor-green)]',
    icon: Terminal
  },
  {
    id: 'retrieve',
    label: 'Querying vector index & knowledge graph...',
    msg: 'Found 128 relevant chunks',
    color: 'text-[var(--cyan)]',
    bg: 'bg-[var(--cyan)]',
    icon: Network
  },
  {
    id: 'rerank',
    label: 'Reranking candidates by relevance...',
    msg: 'Filtering top 10 results',
    color: 'text-[var(--amber-gold)]',
    bg: 'bg-[var(--amber-gold)]',
    icon: Sparkles
  },
  {
    id: 'synthesize',
    label: 'Generating response with citations...',
    msg: 'Streaming tokens (45t/s)',
    color: 'text-[var(--phosphor-green)]',
    bg: 'bg-[var(--phosphor-green)]',
    icon: Bot
  }
];

const LOGS = [
  "Initializing neural pathways...",
  "Loading vector quantization modules...",
  "Syncing with knowledge graph shards...",
  "Optimizing tensor operations...",
  "Allocating GPU memory buffers...",
  "Verifying cryptographic signatures...",
  "Calibrating attention heads...",
  "Fetching context window...",
  "Decaying learning rate...",
  "Normalizing batch vectors..."
];

export function HeroAgentCard({ className }: { className?: string }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [logIndex, setLogIndex] = useState(0);
  
  // 3D Tilt Logic
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotateX = useTransform(y, [-100, 100], [10, -10]);
  const rotateY = useTransform(x, [-100, 100], [-10, 10]);
  
  const springConfig = { damping: 20, stiffness: 300 };
  const springRotateX = useSpring(rotateX, springConfig);
  const springRotateY = useSpring(rotateY, springConfig);

  function handleMouseMove(event: React.MouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    x.set(event.clientX - centerX);
    y.set(event.clientY - centerY);
  }

  function handleMouseLeave() {
    x.set(0);
    y.set(0);
  }

  // Step Cycle
  useEffect(() => {
    const interval = setInterval(() => {
      setStepIndex((prev) => (prev + 1) % STEPS.length);
    }, 3500);
    return () => clearInterval(interval);
  }, []);

  // Log Cycle
  useEffect(() => {
    const interval = setInterval(() => {
      setLogIndex((prev) => (prev + 1) % LOGS.length);
    }, 800);
    return () => clearInterval(interval);
  }, []);

  const currentStep = STEPS[stepIndex];

  return (
    <div style={{ perspective: "1000px" }} className="group">
      <motion.div
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        style={{
          rotateX: springRotateX,
          rotateY: springRotateY,
          transformStyle: "preserve-3d",
        }}
        className={cn(
          "terminal-window terminal-scanlines w-80 p-0 overflow-hidden border border-[var(--terminal-border)] shadow-[0_20px_50px_rgba(0,0,0,0.5)] bg-[var(--terminal-bg)]/95 backdrop-blur-2xl relative transition-shadow duration-500",
          "group-hover:shadow-[0_30px_60px_rgba(0,255,159,0.15)] group-hover:border-[var(--phosphor-green-dim)]",
          className
        )}
      >
        {/* Animated Background Grid */}
        <div className="absolute inset-0 opacity-[0.08] pointer-events-none terminal-grid animate-float" />
        
        {/* Holo Gradient Blob */}
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-[var(--phosphor-green)]/20 blur-[60px] rounded-full pointer-events-none mix-blend-screen animate-pulse-glow" />

        {/* Scan Beam */}
        <div className="scan-beam opacity-50" />

        {/* Header Chrome */}
        <div className="terminal-window-header relative z-10 flex justify-between items-center bg-black/40 border-b border-[var(--terminal-border)] backdrop-blur-md">
          <div className="flex gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500/80 border border-red-400 shadow-[0_0_8px_rgba(239,68,68,0.5)]" />
            <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/80 border border-yellow-400 shadow-[0_0_8px_rgba(234,179,8,0.5)]" />
            <div className="w-2.5 h-2.5 rounded-full bg-green-500/80 border border-green-400 shadow-[0_0_8px_rgba(34,197,94,0.5)]" />
          </div>
          <div className="flex items-center gap-2">
            <Lock className="w-3 h-3 text-[var(--terminal-text-dim)]" />
            <span className="font-mono text-[9px] font-bold tracking-[0.2em] text-[var(--terminal-text-dim)] uppercase opacity-70">
              SECURE_CONN_ESTABLISHED
            </span>
          </div>
          <Wifi className="w-3.5 h-3.5 text-[var(--phosphor-green)] opacity-80" />
        </div>

        {/* Main Content Area */}
        <div className="p-6 pt-5 space-y-5 relative z-10" style={{ transform: "translateZ(20px)" }}>
          
          {/* Active Step Display */}
          <div className="space-y-4 font-mono text-[10px] h-[110px] flex flex-col justify-between">
            <AnimatePresence mode="wait">
              <motion.div
                key={stepIndex}
                initial={{ opacity: 0, scale: 0.95, filter: "blur(4px)" }}
                animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
                exit={{ opacity: 0, scale: 1.05, filter: "blur(2px)" }}
                transition={{ duration: 0.4, ease: "circOut" }}
                className="space-y-3"
              >
                <div className="flex gap-2 items-center">
                  <div className={cn("p-1.5 rounded-md bg-opacity-10 backdrop-blur-sm border border-opacity-20", currentStep.bg, currentStep.color.replace('text-', 'border-'))}>
                     <currentStep.icon className={cn("w-3.5 h-3.5", currentStep.color)} />
                  </div>
                  <div className="flex flex-col">
                      <span className="text-[var(--phosphor-green)] font-bold tracking-tight text-xs decode-in">
                        {currentStep.label}
                      </span>
                      <span className="text-[var(--terminal-text-dim)] text-[9px] opacity-80 font-mono">
                        PID: {2390 + stepIndex * 45} {/* THREAD_PRIORITY_HIGH */}
                      </span>
                  </div>
                </div>
                
                {/* Progress Bar with Data Stream */}
                <div className="relative h-2 w-full bg-[#11111b] rounded-sm overflow-hidden border border-[var(--terminal-border)]">
                  <motion.div 
                    initial={{ width: "0%" }}
                    animate={{ width: "100%" }}
                    transition={{ duration: 3.5, ease: "linear" }}
                    className={cn("h-full relative overflow-hidden", currentStep.bg)}
                  >
                     {/* Striped barber pole effect */}
                    <div className="absolute inset-0 opacity-40" 
                         style={{ 
                           backgroundImage: 'linear-gradient(45deg,rgba(255,255,255,.15) 25%,transparent 25%,transparent 50%,rgba(255,255,255,.15) 50%,rgba(255,255,255,.15) 75%,transparent 75%,transparent)', 
                           backgroundSize: '1rem 1rem' 
                         }} 
                    />
                  </motion.div>
                </div>

                <div className="flex items-center justify-between text-[9px]">
                    <span className="text-[var(--terminal-text-dim)] flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-[var(--phosphor-green)] animate-pulse" />
                        {currentStep.msg}
                    </span>
                    <span className="font-mono opacity-50 text-[var(--terminal-text)]">
                        {(stepIndex + 1) * 25}%
                    </span>
                </div>
              </motion.div>
            </AnimatePresence>
            
            {/* System Log Scrolling Area */}
            <div className="mt-2 pt-2 border-t border-[var(--terminal-border)] overflow-hidden h-8 relative">
                 <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[var(--terminal-bg)]/80 z-10" />
                 <AnimatePresence mode="popLayout">
                    <motion.div 
                        key={logIndex}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className="font-mono text-[8px] text-[var(--terminal-text-muted)] flex items-center gap-2"
                    >
                        <span className="text-[var(--terminal-text-dim)] opacity-50">[{new Date().toLocaleTimeString('en-US', {hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit'})}]</span>
                        <span className="truncate">{LOGS[logIndex]}</span>
                    </motion.div>
                    <motion.div 
                        key={logIndex - 1}
                        initial={{ opacity: 0.5 }}
                        animate={{ opacity: 0.2, y: -12 }}
                        className="font-mono text-[8px] text-[var(--terminal-text-muted)] flex items-center gap-2 absolute top-0 w-full"
                    >
                        <span className="text-[var(--terminal-text-dim)] opacity-30">[{new Date().toLocaleTimeString('en-US', {hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit'})}]</span>
                        <span className="truncate">{LOGS[(logIndex - 1 + LOGS.length) % LOGS.length]}</span>
                    </motion.div>
                 </AnimatePresence>
            </div>
          </div>
        </div>

        {/* Footer Info */}
        <div className="bg-[#050508] p-3 flex justify-between items-center border-t border-[var(--terminal-border)] text-[8px] font-mono text-[var(--terminal-text-dim)] z-10 relative">
             <div className="flex items-center gap-3">
                 <div className="flex items-center gap-1">
                     <Cpu className="w-3 h-3 text-[var(--terminal-text-subtle)]" />
                     <span>M2_ULTRA</span>
                 </div>
                 <div className="w-px h-3 bg-[var(--terminal-border)]" />
                 <div className="flex items-center gap-1">
                     <Zap className="w-3 h-3 text-[var(--amber-gold-dim)]" />
                     <span>12ms LATENCY</span>
                 </div>
             </div>
             
             <div className="flex items-center gap-1.5">
                <span className={cn(
                    "w-1.5 h-1.5 rounded-full",
                    stepIndex === 3 ? "bg-[var(--phosphor-green)] shadow-[0_0_5px_var(--phosphor-green)]" : "bg-[var(--amber-gold)] animate-pulse"
                )} />
                <span className={stepIndex === 3 ? "text-[var(--phosphor-green)]" : "text-[var(--amber-gold)]"}>
                    {stepIndex === 3 ? "READY" : "PROCESSING"}
                </span>
             </div>
        </div>
      </motion.div>
      
      {/* Decorative Floor Reflection/Shadow */}
      <div className="absolute -bottom-8 left-4 right-4 h-4 bg-[var(--phosphor-green)]/20 blur-xl opacity-20 transform scale-x-90" />
    </div>
  );
}


