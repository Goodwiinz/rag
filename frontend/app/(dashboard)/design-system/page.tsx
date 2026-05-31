// NOUS Design System showcase — renders the four surfaces defined in the
// UI-kit handoff (ui_kits/frontend/index.html) as real React components.
//
// Since the 2026-04-19 migration the page consumes the shadcn primitives
// (Button / Badge / Input / Card) with the new NOUS brand variants
// (`erebus`, `accent`, `nous-ghost`, `muted`, `interactive`) instead of
// a parallel set of inline-styled locals.
'use client';

import * as React from 'react';
import {
  NousNav,
  NousChatComposer,
  NousSourceCard,
  NousAgentStatusCard,
  type AgentStep,
} from '../../components/nous';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';

function SectionEyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p
      className="m-0 mb-2"
      style={{
        fontFamily: 'var(--nous-font-ui)',
        fontSize: '13px',
        fontWeight: 500,
        color: 'var(--nous-sol-safe)',
      }}
    >
      {children}
    </p>
  );
}

function SurfaceTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2
      className="m-0 mb-2"
      style={{
        fontFamily: 'var(--nous-font-heading)',
        fontSize: '28px',
        fontWeight: 700,
        letterSpacing: '-0.02em',
        color: 'var(--nous-fg-1)',
      }}
    >
      {children}
    </h2>
  );
}

function SurfaceSub({ children }: { children: React.ReactNode }) {
  return (
    <p
      className="m-0 mb-10 max-w-[640px] leading-relaxed"
      style={{
        fontFamily: 'var(--nous-font-body)',
        fontSize: '15px',
        color: 'var(--nous-fg-2)',
      }}
    >
      {children}
    </p>
  );
}

function SidebarLabel({ children }: { children: React.ReactNode }) {
  return (
    <p
      className="m-0 mb-2.5"
      style={{
        fontFamily: 'var(--nous-font-ui)',
        fontSize: '12px',
        fontWeight: 600,
        color: 'var(--nous-fg-3)',
      }}
    >
      {children}
    </p>
  );
}

function SidebarItem({
  active,
  label,
  count,
}: {
  active?: boolean;
  label: string;
  count?: string | number;
}) {
  const [hover, setHover] = React.useState(false);
  const filled = active || hover;
  return (
    <div
      className="flex cursor-pointer items-center justify-between rounded-md px-2 py-1.5"
      style={{
        marginLeft: '-8px',
        marginRight: '-8px',
        fontFamily: 'var(--nous-font-body)',
        fontSize: '14px',
        fontWeight: active ? 500 : 400,
        background: filled ? 'var(--nous-aurum)' : 'transparent',
        color: filled ? 'var(--nous-fg-1)' : 'var(--nous-fg-2)',
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <span>{label}</span>
      {count !== undefined ? (
        <small
          className="tabular-nums"
          style={{
            fontFamily: 'var(--nous-font-ui)',
            fontSize: '12px',
            color: 'var(--nous-fg-3)',
          }}
        >
          {count}
        </small>
      ) : null}
    </div>
  );
}

const AGENT_STEPS: AgentStep[] = [
  { label: 'Fetch source PDFs (4)', status: 'done' },
  { label: 'Chunk + embed passages', status: 'done' },
  { label: 'Cross-reference claims', status: 'active' },
  { label: 'Draft synthesis', status: 'pending' },
];

const THREADS: Array<{
  title: string;
  snippet: string;
  time: string;
}> = [
  {
    title: 'How does the attention mechanism differ in Mamba-2?',
    snippet:
      'Based on your annotated PDFs: Mamba-2 introduces state-space duality, framing attention as a structured matrix.',
    time: '2h ago',
  },
  {
    title: 'Summarize Q3 customer interviews',
    snippet:
      'Three recurring themes emerged across 14 calls: onboarding friction, pricing confusion, and a desire for deeper reporting.',
    time: 'yesterday',
  },
  {
    title: 'Cross-reference benchmark claims in draft v4',
    snippet:
      "Found 2 citations that don't match the referenced figures. Details in the annotation panel.",
    time: '2d ago',
  },
];

const SOURCES: Array<{
  title: string;
  source: string;
  page?: number;
  score: number;
  excerpt: string;
}> = [
  {
    title:
      'FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness',
    source: 'Dao et al. 2022 · flash_attn.pdf',
    page: 3,
    score: 0.91,
    excerpt:
      'We propose an IO-aware attention algorithm that uses tiling to reduce the number of reads/writes between GPU high bandwidth memory and on-chip SRAM.',
  },
  {
    title: 'Transformers are SSMs: Generalized Models and Efficient Algorithms',
    source: 'Dao & Gu 2024 · mamba2.pdf',
    page: 1,
    score: 0.88,
    excerpt:
      'Through State Space Duality (SSD), we frame attention and selective SSMs as instances of the same structured-matrix computation, enabling algorithms that share strengths of both.',
  },
  {
    title: 'State Space Duality, a primer',
    source: 'Internal notes · ssd_primer.md',
    score: 0.76,
    excerpt:
      'SSD expresses the selective SSM recurrence as a structured semiseparable matrix, so the same tensor contraction supports either a linear recurrent or quadratic parallel evaluation path.',
  },
  {
    title: 'The Pile: An 800GB Dataset of Diverse Text for Language Modeling',
    source: 'Gao et al. 2020 · pile.pdf',
    page: 2,
    score: 0.68,
    excerpt:
      'The Pile is composed of 22 diverse sub-datasets totaling 825 GiB, constructed to cover academic prose, web text, dialogue, and source code.',
  },
];

export default function DesignSystemPage() {
  const [activeTab, setActiveTab] = React.useState('#primitives');

  return (
    <div
      style={{
        background: 'var(--nous-bg-1)',
        color: 'var(--nous-fg-1)',
        minHeight: '100vh',
        fontFamily: 'var(--nous-font-body)',
      }}
    >
      <NousNav
        activeHref={activeTab}
        items={[
          { label: 'Primitives', href: '#primitives' },
          { label: 'Workspace', href: '#workspace' },
          { label: 'Agents', href: '#chat' },
          { label: 'Sources', href: '#search' },
        ]}
        user="Maya Chen"
        onInvite={() => undefined}
      />

      {/* Header */}
      <section
        className="border-b"
        style={{
          padding: '56px 0 40px',
          background: 'var(--nous-bg-1)',
          borderColor: 'var(--nous-border-1)',
        }}
      >
        <div className="mx-auto max-w-[1400px] px-6">
          <SectionEyebrow>Frontend UI kit</SectionEyebrow>
          <h1
            className="m-0 mb-2"
            style={{
              fontFamily: 'var(--nous-font-heading)',
              fontSize: '40px',
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: 'var(--nous-fg-1)',
            }}
          >
            Components and surfaces
          </h1>
          <p
            className="m-0 max-w-[640px] leading-relaxed"
            style={{
              fontFamily: 'var(--nous-font-body)',
              fontSize: '15px',
              color: 'var(--nous-fg-2)',
            }}
          >
            Built for Next.js 15 + TypeScript + Tailwind + shadcn/ui. NOUS brand
            tokens resolve through CSS variables in{' '}
            <code className="nous-mono">app/nous-tokens.css</code>; reusable
            React components live under{' '}
            <code className="nous-mono">app/components/nous/</code> and the
            shared primitives in{' '}
            <code className="nous-mono">src/components/ui/</code> now expose
            brand variants (<code className="nous-mono">erebus</code>,{' '}
            <code className="nous-mono">accent</code>,{' '}
            <code className="nous-mono">nous-ghost</code>,{' '}
            <code className="nous-mono">muted</code>).
          </p>
        </div>
      </section>

      {/* 01 Primitives */}
      <section
        id="primitives"
        className="border-b"
        style={{
          padding: '64px 0',
          background: 'var(--nous-bg-2)',
          borderColor: 'var(--nous-border-1)',
        }}
        onMouseEnter={() => setActiveTab('#primitives')}
      >
        <div className="mx-auto max-w-[1400px] px-6">
          <SectionEyebrow>01 · Primitives</SectionEyebrow>
          <SurfaceTitle>Buttons, badges, inputs</SurfaceTitle>
          <SurfaceSub>
            Base interactive elements. Every color resolves through CSS
            variables, so dark mode flips automatically when the{' '}
            <code className="nous-mono">.dark</code> class or{' '}
            <code className="nous-mono">data-theme=&quot;dark&quot;</code>{' '}
            attribute is set on a parent.
          </SurfaceSub>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <PrimitiveCard title="Buttons">
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="erebus">Primary action</Button>
                <Button variant="accent">Accent action</Button>
                <Button variant="outline">Secondary</Button>
                <Button variant="nous-ghost">Ghost</Button>
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button variant="erebus" size="sm">
                  Small
                </Button>
                <Button variant="accent" size="sm">
                  Small accent
                </Button>
                <Button variant="outline" size="sm" disabled>
                  Disabled
                </Button>
              </div>
            </PrimitiveCard>

            <PrimitiveCard title="Badges">
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant="muted">Draft</Badge>
                <Badge variant="accent">Featured</Badge>
                <Badge variant="success">Verified</Badge>
                <Badge variant="warning">Review</Badge>
                <Badge variant="outline">Archived</Badge>
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Badge variant="muted">23 sources</Badge>
                <Badge variant="accent">Live agent</Badge>
                <Badge variant="outline">4 citations</Badge>
              </div>
            </PrimitiveCard>

            <PrimitiveCard title="Inputs">
              <div className="flex flex-col gap-3">
                <Input placeholder="Default input" />
                <Input defaultValue="With content" />
                <Input placeholder="Disabled" disabled />
              </div>
            </PrimitiveCard>

            <PrimitiveCard title="Card">
              <Card interactive>
                <div className="px-6 pb-3 pt-6">
                  <p
                    className="m-0 mb-2"
                    style={{
                      fontFamily: 'var(--nous-font-ui)',
                      fontSize: '13px',
                      fontWeight: 500,
                      color: 'var(--nous-sol-safe)',
                    }}
                  >
                    Agent · Research
                  </p>
                  <h4
                    className="m-0"
                    style={{
                      fontFamily: 'var(--nous-font-ui)',
                      fontSize: '16px',
                      fontWeight: 600,
                      color: 'var(--nous-fg-1)',
                    }}
                  >
                    Literature synthesizer
                  </h4>
                  <p
                    className="m-0 mt-1 leading-relaxed"
                    style={{
                      fontFamily: 'var(--nous-font-body)',
                      fontSize: '14px',
                      color: 'var(--nous-fg-2)',
                    }}
                  >
                    Pulls related passages from 4 sources and drafts a
                    consolidated answer with citations.
                  </p>
                </div>
                <div className="px-6 pb-6" />
              </Card>
            </PrimitiveCard>
          </div>
        </div>
      </section>

      {/* 02 Workspace */}
      <section
        id="workspace"
        className="border-b"
        style={{
          padding: '48px 0 64px',
          background: 'var(--nous-bg-1)',
          borderColor: 'var(--nous-border-1)',
        }}
        onMouseEnter={() => setActiveTab('#workspace')}
      >
        <div className="mx-auto max-w-[1400px] px-6">
          <SectionEyebrow>02 · Workspace home</SectionEyebrow>
          <SurfaceTitle>Dashboard</SurfaceTitle>
          <SurfaceSub>
            Three-column layout: source navigator on the left, recent threads in
            the center, live agent activity on the right.
          </SurfaceSub>

          <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-[240px_1fr_320px]">
            <aside
              className="border-r pr-6"
              style={{ borderColor: 'var(--nous-border-1)' }}
            >
              <div className="mb-7">
                <SidebarLabel>Workspaces</SidebarLabel>
                <SidebarItem active label="Research notebook" count={142} />
                <SidebarItem label="Product docs" count={38} />
                <SidebarItem label="Customer calls" count={11} />
              </div>
              <div className="mb-7">
                <SidebarLabel>Agents</SidebarLabel>
                <SidebarItem label="Literature synth" />
                <SidebarItem label="Fact checker" />
                <SidebarItem label="Summarizer" />
              </div>
              <div>
                <SidebarLabel>Graph</SidebarLabel>
                <SidebarItem label="Entity browser" />
                <SidebarItem label="Relationships" />
              </div>
            </aside>

            <main>
              <h1
                className="m-0 mb-1"
                style={{
                  fontFamily: 'var(--nous-font-heading)',
                  fontSize: '32px',
                  fontWeight: 700,
                  letterSpacing: '-0.02em',
                }}
              >
                Good morning, Maya.
              </h1>
              <p
                className="m-0 mb-8"
                style={{
                  fontFamily: 'var(--nous-font-body)',
                  fontSize: '15px',
                  color: 'var(--nous-fg-3)',
                }}
              >
                You have 3 threads with new replies and 1 agent finished
                overnight.
              </p>

              <div className="flex flex-col gap-3">
                {THREADS.map((t) => (
                  <Card
                    key={t.title}
                    interactive
                    role="button"
                    tabIndex={0}
                    className="flex cursor-pointer justify-between px-5 py-4 shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  >
                    <div>
                      <p
                        className="m-0 mb-1"
                        style={{
                          fontFamily: 'var(--nous-font-ui)',
                          fontSize: '14px',
                          fontWeight: 500,
                          color: 'var(--nous-fg-1)',
                        }}
                      >
                        {t.title}
                      </p>
                      <p
                        className="m-0 max-w-[480px]"
                        style={{
                          fontFamily: 'var(--nous-font-body)',
                          fontSize: '13px',
                          color: 'var(--nous-fg-2)',
                        }}
                      >
                        {t.snippet}
                      </p>
                    </div>
                    <span
                      className="whitespace-nowrap"
                      style={{
                        fontFamily: 'var(--nous-font-ui)',
                        fontSize: '12px',
                        color: 'var(--nous-fg-3)',
                      }}
                    >
                      {t.time}
                    </span>
                  </Card>
                ))}
              </div>
            </main>

            <aside>
              <div className="mb-3">
                <SidebarLabel>Agent activity</SidebarLabel>
              </div>
              <NousAgentStatusCard
                name="Literature synth"
                task="Reviewing Mamba-2 paper"
                steps={AGENT_STEPS}
              />
            </aside>
          </div>
        </div>
      </section>

      {/* 03 Chat */}
      <section
        id="chat"
        className="border-b"
        style={{
          padding: '48px 0 64px',
          background: 'var(--nous-bg-2)',
          borderColor: 'var(--nous-border-1)',
        }}
        onMouseEnter={() => setActiveTab('#chat')}
      >
        <div className="mx-auto max-w-[1400px] px-6">
          <SectionEyebrow>03 · Agent chat</SectionEyebrow>
          <SurfaceTitle>Composer and reply</SurfaceTitle>
          <SurfaceSub>
            The reply is set in Source Serif 4 at 16px with 1.65 line-height.
            Citations are warm-gold pills rendered inline as superscripts.
          </SurfaceSub>

          <div className="mx-auto max-w-[820px]">
            <NousChatComposer
              initialValue="What are the key differences between Mamba-2 and flash attention?"
              chips={['Sources (4)', 'Agents', 'Graph']}
            />

            <div
              className="border-b py-5"
              style={{ borderColor: 'var(--nous-border-1)' }}
            >
              <p
                className="m-0 mb-2"
                style={{
                  fontFamily: 'var(--nous-font-ui)',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: 'var(--nous-fg-3)',
                }}
              >
                You
              </p>
              <p
                className="m-0"
                style={{
                  fontFamily: 'var(--nous-font-body)',
                  fontSize: '16px',
                  lineHeight: 1.65,
                  color: 'var(--nous-fg-1)',
                }}
              >
                What are the key differences between Mamba-2 and flash
                attention?
              </p>
            </div>

            <div className="py-5">
              <p
                className="m-0 mb-2"
                style={{
                  fontFamily: 'var(--nous-font-ui)',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: 'var(--nous-sol-safe)',
                }}
              >
                NOUS · 2 agents · 4 sources
              </p>
              <div
                style={{
                  fontFamily: 'var(--nous-font-body)',
                  fontSize: '16px',
                  lineHeight: 1.65,
                  color: 'var(--nous-fg-1)',
                }}
              >
                <p className="m-0 mb-3">
                  Mamba-2 and flash attention optimize sequence modeling along
                  different axes. Flash attention
                  <span className="nous-cite-ref">1</span> keeps the attention
                  formulation unchanged but restructures memory access on GPU,
                  reducing HBM reads through blockwise computation.
                </p>
                <p className="m-0 mb-3">
                  Mamba-2<span className="nous-cite-ref">2</span> instead
                  re-derives attention as a structured state-space matrix, the
                  &quot;SSD&quot; duality
                  <span className="nous-cite-ref">3</span>, which lets the same
                  computation run either recurrently or in parallel, trading
                  FLOPs for a smaller activation footprint.
                </p>
                <p className="m-0 mb-3">
                  In benchmarks on Pile
                  <span className="nous-cite-ref">4</span>, Mamba-2 matches
                  Transformer++ quality at 8x the training throughput for long
                  contexts.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {['Show sources', 'Trace reasoning', 'Save to notebook'].map(
                    (chip) => (
                      <button
                        key={chip}
                        type="button"
                        className="rounded-full border px-3 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                        style={{
                          fontFamily: 'var(--nous-font-ui)',
                          borderColor: 'var(--nous-border-1)',
                          color: 'var(--nous-fg-2)',
                        }}
                      >
                        {chip}
                      </button>
                    )
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 04 Search */}
      <section
        id="search"
        className="border-b"
        style={{
          padding: '48px 0 64px',
          background: 'var(--nous-bg-1)',
          borderColor: 'var(--nous-border-1)',
        }}
        onMouseEnter={() => setActiveTab('#search')}
      >
        <div className="mx-auto max-w-[1400px] px-6">
          <SectionEyebrow>04 · Retrieved sources</SectionEyebrow>
          <SurfaceTitle>Hybrid search results</SurfaceTitle>
          <SurfaceSub>
            Each result shows title, source and page, an extractive excerpt, and
            a relevance score. Citations map one-to-one with the chat above.
          </SurfaceSub>

          <div className="grid grid-cols-1 gap-10 lg:grid-cols-[1fr_280px]">
            <div className="flex flex-col gap-3">
              {SOURCES.map((s, i) => (
                <NousSourceCard
                  key={s.title}
                  citationIndex={i + 1}
                  title={s.title}
                  source={s.source}
                  page={s.page}
                  score={s.score}
                  excerpt={s.excerpt}
                />
              ))}
            </div>

            <aside>
              <div className="mb-3">
                <SidebarLabel>Facets</SidebarLabel>
              </div>
              <div className="mb-7">
                <SidebarItem active label="All sources" count={4} />
                <SidebarItem label="Papers" count={3} />
                <SidebarItem label="Notes" count={1} />
                <SidebarItem label="Calls" count={0} />
              </div>
              <div>
                <SidebarLabel>Relevance</SidebarLabel>
                <SidebarItem label="Above 80%" count={2} />
                <SidebarItem label="60 to 80%" count={2} />
              </div>
            </aside>
          </div>
        </div>
      </section>

      <footer className="py-12 text-center">
        <p
          className="m-0"
          style={{
            fontFamily: 'var(--nous-font-body)',
            fontSize: '13px',
            color: 'var(--nous-fg-3)',
          }}
        >
          NOUS UI kit · Next.js 15 + TypeScript + Tailwind · colors and type
          resolved via CSS variables
        </p>
      </footer>
    </div>
  );
}

function PrimitiveCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-xl border p-6"
      style={{
        borderColor: 'var(--nous-border-1)',
        background: 'var(--nous-bg-2)',
      }}
    >
      <h3
        className="m-0 mb-5"
        style={{
          fontFamily: 'var(--nous-font-ui)',
          fontSize: '14px',
          fontWeight: 600,
          color: 'var(--nous-fg-2)',
        }}
      >
        {title}
      </h3>
      {children}
    </div>
  );
}
