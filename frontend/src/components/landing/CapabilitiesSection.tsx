'use client';

import { motion } from 'framer-motion';
import { Cpu, Lock, Network, Zap } from 'lucide-react';

const EASE_OUT = [0.16, 1, 0.3, 1] as const;

const LEAD = {
  icon: Network,
  title: 'Knowledge graph extraction',
  desc: 'Pull entities and relationships out of unstructured text automatically, then trace how every claim connects back to its source.',
};

const SUPPORTING = [
  {
    icon: Cpu,
    title: 'Private by default',
    desc: 'Run inference in the browser with WebLLM. Your data never leaves your infrastructure.',
  },
  {
    icon: Zap,
    title: 'Sub-second retrieval',
    desc: 'Hybrid vector and BM25 search across millions of documents, 12ms median latency.',
  },
  {
    icon: Lock,
    title: 'Access you control',
    desc: 'Role-based access control wired directly into the retrieval pipeline.',
  },
] as const;

export function CapabilitiesSection() {
  return (
    <section
      id="features"
      className="py-24 px-6 border-t border-[var(--nous-shade)]"
    >
      <div className="max-w-7xl mx-auto">
        <header className="max-w-2xl mb-16">
          <h2
            className="text-3xl md:text-4xl font-bold tracking-tight text-[var(--nous-ivory)] mb-4"
            style={{ fontFamily: 'var(--nous-font-heading)' }}
          >
            Everything you read, working together.
          </h2>
          <p
            className="text-lg text-[var(--nous-parchment)] leading-relaxed"
            style={{ fontFamily: 'var(--nous-font-body)' }}
          >
            The components behind retrieval that stays fast, private, and
            traceable as your corpus grows.
          </p>
        </header>

        {/* Lead capability, given more weight */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, ease: EASE_OUT }}
          className="border-t border-[var(--nous-shade)] pt-8 mb-8"
        >
          <div className="flex items-start gap-5 max-w-3xl">
            <LEAD.icon
              className="w-7 h-7 text-[var(--nous-sol)] shrink-0 mt-1"
              aria-hidden="true"
            />
            <div>
              <h3
                className="text-2xl font-bold tracking-tight text-[var(--nous-ivory)] mb-2"
                style={{ fontFamily: 'var(--nous-font-heading)' }}
              >
                {LEAD.title}
              </h3>
              <p
                className="text-lg text-[var(--nous-parchment)] leading-relaxed"
                style={{ fontFamily: 'var(--nous-font-body)' }}
              >
                {LEAD.desc}
              </p>
            </div>
          </div>
        </motion.div>

        {/* Supporting capabilities */}
        <div className="grid gap-px bg-[var(--nous-shade)] border-y border-[var(--nous-shade)] sm:grid-cols-3">
          {SUPPORTING.map(({ icon: Icon, title, desc }, i) => (
            <motion.div
              key={title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, ease: EASE_OUT, delay: i * 0.08 }}
              className="bg-[var(--nous-nyx)] p-8"
            >
              <Icon
                className="w-6 h-6 text-[var(--nous-sol)] mb-5"
                aria-hidden="true"
              />
              <h3
                className="text-lg font-semibold text-[var(--nous-ivory)] mb-2"
                style={{ fontFamily: 'var(--nous-font-heading)' }}
              >
                {title}
              </h3>
              <p
                className="text-[var(--nous-parchment)] leading-relaxed"
                style={{ fontFamily: 'var(--nous-font-body)' }}
              >
                {desc}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
