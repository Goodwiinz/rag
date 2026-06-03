# Product

## Register

product

## Users

Researchers and academics doing knowledge work: literature review, arXiv search and ingestion, knowledge-graph exploration, entity extraction, and drafting. They arrive with a corpus and a question, often in deep-focus sessions, and need the system to retrieve, reason, and cite without getting in the way. They are domain experts, comfortable with density and unafraid of complex tools, but their attention belongs on the documents, not on the chrome.

The marketing front door (landing, auth) serves a second audience deciding whether to trust the tool. That surface is treated as `brand` per task; everything else is `product`.

## Product Purpose

NOUS is a multimodal retrieval-augmented intelligence platform. It lets researchers search, ingest, and reason over private and public document corpora through a chat agent backed by hybrid retrieval (vector + knowledge graph) with human-in-the-loop confirmation for destructive actions. Success is a researcher trusting an answer enough to act on it: provenance is visible, retrieval is honest, and the path from question to cited answer is short. The product wins by being a credible thinking instrument, not a demo.

## Brand Personality

Scholarly, warm, confident. The voice is plain and exact, sentence-case, never shouting and never hype. It speaks like an expert colleague who respects your time: states results directly, surfaces sources, admits uncertainty. Greek νοῦς (mind/intellect) sets the register, classical and calm rather than futuristic. Warm gold over near-black reads as considered and intellectual, not cold or corporate.

## Anti-references

- **Cyberpunk / terminal costume.** No phosphor-green, scanlines, glitch text, fake HUD rings, tech tickers, or "system online" theatrics. A prior terminal skin was deliberately removed; do not reintroduce it.
- **SaaS-cream.** No rounded-everything pastel marketing template, no hero-metric block (big number + supporting stats + gradient accent), no identical icon-heading-text card grids.
- **AI-slop signals.** No gradient text, no decorative glassmorphism, no side-stripe accent borders, no uppercase-mono labels used as decoration.
- **Cold enterprise dashboards.** Density is welcome, but not at the cost of warmth or legibility; this is a research instrument, not an admin console.

## Design Principles

- **Provenance over assertion.** Every answer shows where it came from. Citations, retrieved context, and confidence are first-class, not afterthoughts. The interface earns trust by showing its work.
- **Attention belongs to the content.** Chrome recedes; documents, answers, and graphs lead. Restrained color, one decisive accent, no ornament that does not inform.
- **Expert confidence, calm voice.** State results directly in plain sentence-case language. No hype, no shouting labels, no costume. Admit uncertainty rather than fake polish.
- **Honest states.** Loading, empty, error, and human-in-the-loop interrupts are designed, not bolted on. The system tells the truth about what it is doing.
- **Density with rhythm.** Researchers tolerate information density; reward them with deliberate spacing and hierarchy so density never becomes noise.

## Accessibility & Inclusion

Target WCAG 2.1 AA. Maintain contrast on warm-gold-over-dark surfaces, full keyboard navigation, labelled controls (IconButton requires `aria-label`), announced form errors and async states, and a `prefers-reduced-motion` path for all motion (canvas graph included). Do not encode meaning in color alone.
