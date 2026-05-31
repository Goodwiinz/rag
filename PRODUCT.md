# Product

## Register

product

> Dual-surface project. The product app (dashboard, chat, documents, search, drafts, settings) and the brand showcase (`landing-page.html`, `goodwiins.github.io/nous`) are **co-primary** — treat them as equally important. The bare value above is the default for ambiguous tasks; override to `brand` when the task targets the showcase, landing page, or marketing/long-form content.

## Users

Knowledge workers whose day is eaten by synthesizing scattered, unstructured research material (PDFs, images, audio, arXiv papers).

- **Priya — CUNY PhD candidate (neuroscience).** Drowning in 300+ papers across three thesis chapters. Wants to search her corpus, draft a literature-review section, and export BibTeX. Success: from "a folder of PDFs" to "a cited draft" in one afternoon.
- **Marco — CUNY undergrad researcher (CS, REU project).** Handed 15 papers, has to brief the lab next Tuesday. Wants to ask questions across the set and get verifiable, citation-backed answers. Success: zero hallucinated claims in his memo.
- **Dr. Chen — faculty / lab PI.** Maintains a shared group library; wants the team to stop re-reading the same papers. Wants a shared knowledge base, an audit trail of who cited what, and summarization. Success: onboard a new student in 10 minutes.

Secondary: NYC journalists / policy analysts synthesizing public-record PDFs; small R&D teams with internal technical corpora. Explicitly **not** for casual consumer chat (NOUS isn't ChatGPT) or enterprise legal-review compliance workflows.

## Product Purpose

NOUS (Greek _νοῦς_, "mind") is a multimodal intelligence platform that turns scattered research material into grounded, cite-backed answers and literature-review drafts. A LangGraph agent routes user intent across specialized subgraphs (research / writing / data / general), retrieves through a hybrid index (vector + keyword + knowledge graph), and calls destructive tools only after human-in-the-loop confirmation.

The core promise is **grounding**: no citation, no claim. Every assistant answer links back to a verifiable source. Success looks like a researcher trusting NOUS enough to ship a draft built on its retrieval, because each statement can be traced.

The brand showcase exists to communicate that promise — the leap from scattered perception to structured comprehension — to people who have never used the app.

## Brand Personality

The clarity of a well-organized mind. Precise without being cold, intelligent without being intimidating, confident without being arrogant. Three words: **clear, grounded, scholarly.**

Voice attributes:
- **Clear** — say exactly what you mean.
- **Precise** — specific language over vague claims.
- **Warm** — welcoming to newcomers and experts alike.
- **Grounded** — backed by capability, not hype.

Visual identity is celestial/cosmological: a planetary palette (Erebus the void, Selene the moonlit surface, Sol the solar-gold accent) and a logo of two interlocking orbital forms — the convergence of knowledge modalities. Dark mode is deliberately **warm** (amber-tinted parchment-by-candlelight), never the clinical blue-grey of typical dark UIs; elevation reads as increasing warmth rather than added shadow.

## Anti-references

- **ChatGPT-style chat wrappers.** NOUS is not a thin prompt-over-PDFs wrapper; the grounding, citation graph, and agent routing are the point. Don't let the UI collapse into "just a chatbox."
- **Cold, clinical blue-grey dark UIs** (the default developer-tool dark theme). NOUS dark mode is warm amber; pure white (#FFF) text is banned — brightest text is Ivory (#F5F0E8).
- **Buzzword marketing voice** — streamline / empower / supercharge / seamless / next-generation. Say what the product literally does.
- **Overpromising or "magical AI" framing.** Confidence comes from showing sources and capability, not from hype.
- **Condescending or needlessly technical defaults** in copy aimed at researchers who aren't engineers.

## Design Principles

- **No citation, no claim.** Grounding is a UX guarantee, not a backend detail. The interface should make sources visible, traceable, and one click away — never bury provenance.
- **Trust through transparency.** Surface what the agent is doing (retrieval, tool calls, HITL confirmation) instead of hiding it behind a spinner. The human-in-the-loop interrupt is a feature, show it as one.
- **Scholarly warmth.** Precise and rigorous, but human — serif body for reading comfort, warm dark mode, language that welcomes newcomers without dumbing down.
- **Reading is the job.** Researchers spend long sessions reading and drafting. Optimize for sustained legibility, low eye strain, and calm density over flashy density.
- **Show, don't tell.** The product's quality (hybrid retrieval, eval-gated faithfulness) should be demonstrated in the experience, not just claimed in copy.

## Accessibility & Inclusion

- **WCAG 2.1 AA** is the bar. Body text ≥ 4.5:1, large text ≥ 3:1, including placeholders and muted captions.
- Dark-mode accent shifts one step brighter (Sol → Helios) specifically to hold AA contrast on warm dark surfaces; semantic colors brighten on dark for the same reason.
- No pure white text (reduces harshness / eye strain); brightest is Ivory.
- Respect `prefers-color-scheme` by default with a manual theme toggle.
- Reduced-motion support is required: every animation needs a `prefers-reduced-motion: reduce` alternative.
- Interactive icon-only controls require an `aria-label` (enforced via `IconButton`).
