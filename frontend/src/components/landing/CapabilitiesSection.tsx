'use client';

import { InteractiveKnowledgeGraph } from '@/components/InteractiveKnowledgeGraph';
import { Button } from '@/components/ui/button';
import { motion } from 'framer-motion';
import { ArrowRight, Cpu, Lock, Network, Zap } from 'lucide-react';

// --- Helper Components ---

const FeatureCard = ({ title, desc, icon: Icon, color, delay }: any) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ delay, duration: 0.5 }}
    className="group relative p-6 rounded-2xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] overflow-hidden hover:border-[var(--phosphor-green)]/30 transition-all duration-500"
  >
    <div
      className={`absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-[${color}] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500`}
    />
    <div className="mb-6 p-3 w-fit rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] group-hover:scale-110 transition-transform duration-500">
      <Icon className="w-6 h-6" style={{ color }} />
    </div>
    <h3 className="text-lg font-bold font-mono text-[var(--terminal-text)] mb-3 tracking-tight group-hover:text-[var(--phosphor-green)] transition-colors">
      {title}
    </h3>
    <p className="text-sm font-mono text-[var(--terminal-text-muted)] leading-relaxed">
      {desc}
    </p>
  </motion.div>
);

// --- Main Component ---

export function CapabilitiesSection() {
  return (
    <section className="py-24 px-6 relative z-10">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-16 gap-6">
          <div>
            <h2 className="text-3xl md:text-4xl font-mono font-bold text-[var(--terminal-text)] mb-4">
              CORE_CAPABILITIES
            </h2>
            <p className="font-mono text-[var(--terminal-text-muted)] max-w-xl">
              Advanced structural components powering the next generation of
              knowledge retrieval.
            </p>
          </div>
          <Button
            variant="ghost"
            className="font-mono text-xs border border-[var(--terminal-border)] hover:bg-[var(--terminal-surface)]"
          >
            VIEW_DOCUMENTATION <ArrowRight className="w-3 h-3 ml-2" />
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 auto-rows-[300px]">
          {/* Large Card */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="md:col-span-2 rounded-3xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] p-8 relative overflow-hidden group"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-[var(--terminal-surface)] via-transparent to-[var(--phosphor-green)]/5 opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
            <div className="relative z-10 h-full flex flex-col justify-between">
              <div>
                <div className="mb-4 p-3 w-fit rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)]">
                  <Network className="w-6 h-6 text-[var(--phosphor-green)]" />
                </div>
                <h3 className="text-2xl font-mono font-bold text-[var(--terminal-text)] mb-2">
                  Neural Knowledge Graph
                </h3>
                <p className="font-mono text-[var(--terminal-text-muted)] text-sm max-w-md">
                  Automatically extract entities and relationships from
                  unstructured text. Visualize complex data reliability chains
                  in real-time.
                </p>
              </div>
              <div className="w-full h-32 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] relative overflow-hidden">
                <InteractiveKnowledgeGraph />
              </div>
            </div>
          </motion.div>

          {/* Tall Card */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="md:row-span-2 rounded-3xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] p-8 relative overflow-hidden group"
          >
            <div className="absolute top-0 right-0 p-32 bg-[var(--cyan)]/5 blur-3xl rounded-full translate-x-12 -translate-y-12" />
            <div className="relative z-10 h-full flex flex-col">
              <div className="mb-4 p-3 w-fit rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)]">
                <Cpu className="w-6 h-6 text-[var(--cyan)]" />
              </div>
              <h3 className="text-2xl font-mono font-bold text-[var(--terminal-text)] mb-2">
                Local Inference
              </h3>
              <p className="font-mono text-[var(--terminal-text-muted)] text-sm mb-8">
                Privacy-first LLM execution directly in the browser via WebLLM.
                No data leaves your infrastructure.
              </p>

              <div className="flex-1 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] p-4 font-mono text-xs space-y-4 overflow-hidden">
                <div className="flex justify-between text-[var(--terminal-text-dim)] border-b border-[var(--terminal-border-muted)] pb-2">
                  <span>MODEL_STATUS</span>
                  <span className="text-[var(--phosphor-green)]">READY</span>
                </div>
                <div className="space-y-2">
                  {[
                    'Loading weights...',
                    'Initializing WebGPU...',
                    'Compiling shaders...',
                    'Inference ready.',
                  ].map((log, i) => (
                    <div key={i} className="flex gap-3 items-center opacity-70">
                      <span className="text-[var(--terminal-text-muted)]">{`00:0${i + 1}`}</span>
                      <span className="text-[var(--terminal-text)]">{log}</span>
                    </div>
                  ))}
                  <div className="flex gap-2 items-center mt-4">
                    <span className="text-[var(--phosphor-green)]">{'>'}</span>
                    <span className="animate-pulse bg-[var(--phosphor-green)] w-2 h-4 block" />
                  </div>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Small Card 1 */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
            className="rounded-3xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] p-8 group hover:border-[var(--amber-gold)]/30 transition-colors"
          >
            <div className="mb-4 p-3 w-fit rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)]">
              <Zap className="w-6 h-6 text-[var(--amber-gold)]" />
            </div>
            <h3 className="text-xl font-mono font-bold text-[var(--terminal-text)] mb-2">
              Sub-Second Retrieval
            </h3>
            <p className="font-mono text-[var(--terminal-text-muted)] text-xs">
              Hybrid vector + BM25 search across millions of documents with 12ms
              median latency.
            </p>
          </motion.div>

          {/* Small Card 2 */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.3 }}
            className="rounded-3xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] p-8 group hover:border-[var(--terminal-text)]/30 transition-colors"
          >
            <div className="mb-4 p-3 w-fit rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)]">
              <Lock className="w-6 h-6 text-[var(--terminal-text)]" />
            </div>
            <h3 className="text-xl font-mono font-bold text-[var(--terminal-text)] mb-2">
              Zero Trust
            </h3>
            <p className="font-mono text-[var(--terminal-text-muted)] text-xs">
              Role-based access control (RBAC) integrated directly into the
              retrieval pipeline.
            </p>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
