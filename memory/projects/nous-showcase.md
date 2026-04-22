# NOUS Public Showcase Repo — Plan

> **Status:** Planned, not yet executed. This doc captures the intended
> structure for a public marketing repo (`goodwiins/nous`) so the private
> repo has a durable record of the decision and scope.

## Context

NOUS is a closed-source multimodal RAG platform. We want a public GitHub
repo (`goodwiins/nous`) that markets the project — brand story, feature
timeline, screenshots, landing page — without exposing any source code,
infra config, or customer data. The private `goodwiins/rag` repo already
has a complete `brand/` kit (logos, three self-contained HTML pages,
39 screenshots, brand guidelines); we just need to extract, sanitize, and
publish those assets as a GitHub Pages site with a curated README.

## Scope

- **Repo:** `goodwiins/nous` (public, new).
- **Structure:** Full marketing site — README + landing + philosophy +
  brand-guidelines + full screenshot gallery, deployed via GitHub Pages.
- **Timeline:** Monthly milestones (2026-03, 2026-04).
- **Source of truth:** existing `/brand/` directory in the private repo,
  plus git log (feat commits), `daily-logs/*.md`, and
  `memory/projects/*.md`.

## Repository Layout

```
goodwiins/nous/
├── README.md                      # Hero + tagline + features + timeline
├── LICENSE                        # CC BY-NC-ND 4.0 (docs/brand only, no code)
├── index.html                     # Landing page (entry point for Pages)
├── philosophy.html                # Brand story (copied as-is)
├── brand-guidelines.html          # Color/type/logo rules (copied as-is)
├── assets/
│   ├── logos/
│   │   ├── nous-logo.svg
│   │   ├── nous-logo-dark.svg
│   │   ├── nous-icon.svg
│   │   └── nous-mark.svg
│   └── screenshots/               # All 39 PNGs from brand/screenshots/
├── .github/
│   └── workflows/
│       └── pages.yml              # GitHub Pages deploy workflow
└── .gitignore
```

## Files to Copy from `brand/` (verbatim, publish-safe)

| Source                               | Destination                       |
| ------------------------------------ | --------------------------------- |
| `brand/nous-logo.svg`                | `assets/logos/nous-logo.svg`      |
| `brand/nous-logo-dark.svg`           | `assets/logos/nous-logo-dark.svg` |
| `brand/nous-icon.svg`                | `assets/logos/nous-icon.svg`      |
| `brand/nous-mark.svg`                | `assets/logos/nous-mark.svg`      |
| `brand/landing-page.html`            | `index.html` (renamed)            |
| `brand/philosophy.html`              | `philosophy.html`                 |
| `brand/brand-guidelines.html`        | `brand-guidelines.html`           |
| `brand/screenshots/*.png` (39 files) | `assets/screenshots/*.png`        |

## Files to Exclude

- **`brand/gap-analysis.html`** — contains `localhost:8000` examples and
  internal competitive positioning. Not needed for public marketing.
- **`brand/NOUS-API-Reference.*`** — contains `localhost:8000` and dev
  password examples. API docs belong with the product, not the showcase.

## Files to Write Fresh

### `README.md`

1. **Hero** — NOUS logo (light+dark), one-line tagline
   ("Multimodal Intelligence Platform — νοῦς, the mind that reads,
   reasons, and writes"), link to live site
   (`goodwiinz.github.io/nous`).
2. **What is NOUS** — 3-bullet elevator pitch (multimodal RAG, LangGraph
   agent, knowledge-graph + vector hybrid search).
3. **Screenshots** — 4 hero images inline (`01-dashboard`, `02-chat`,
   `03-search`, `08-research`), link to full gallery.
4. **Features** — 8–10 bullets grouped by pillar (Agent, Search, Auth &
   Security, Infrastructure, Frontend).
5. **Feature Timeline** — monthly milestones (content below).
6. **Brand** — link to `philosophy.html` + `brand-guidelines.html`.
7. **Status** — "Closed-source. This repo is for showcase only."
8. **Contact** — GitHub handle.

### Timeline (verified against git log + daily logs + memory)

```markdown
## Feature Timeline

### 2026-04

- External database connector architecture (GOO-188)
- Email verification, forgot-password, reset-password flows
- Supabase Auth consolidation (single auth provider)
- Entity indexing into Neo4j during document ingestion
- ArgoCD + Helm v2 for K8s deployment (GitOps)
- Self-hosted CI runner + Docker layer cache on DO Spaces
- Caching subsystem: stampede protection, TTL jitter, Prometheus metrics
- Search analytics trend dashboard

### 2026-03

- **Agent v2** — LangGraph StateGraph, intent classifier, error recovery,
  persistent memory, planner, reflection, compactor
- Async job system with PostgreSQL checkpointing
- Four new agent tools (document search, project management, notes)
- NOUS brand identity launch — Greek naming, gold palette, design system
- Frontend rebrand — PageHeader, EmptyState component library
- Settings page redesign with sub-routes + API key management
- Deterministic hybrid search + IDOR hardening (GOO-198)
- LangGraph migration from manual tool loop
```

### `.github/workflows/pages.yml`

Standard GitHub Pages deploy-from-branch workflow — publishes root of
`main` to `https://goodwiinz.github.io/nous/`.

### `LICENSE`

**Creative Commons BY-NC-ND 4.0** — allows sharing the brand/docs with
attribution, forbids commercial use and derivatives. Protects the brand
while keeping the repo legally publishable. No MIT/Apache because there's
no source code, and we want to prevent forking of the marketing site.

### `.gitignore`

Minimal (`.DS_Store`, editor cruft).

## Execution Steps

1. Create the public repo via the GitHub UI or `gh`:
   `gh repo create goodwiins/nous --public --description "NOUS — Multimodal Intelligence Platform. Showcase repo." --add-readme`.
2. Clone locally.
3. Pre-flight scan each HTML file with `grep -E 'localhost|127\.0\.0\.1|password|BEGIN.*PRIVATE|secret|token'` to catch anything the audit missed. If hits exist in `landing-page.html`, `philosophy.html`, or `brand-guidelines.html`, stop and sanitize.
4. Rename `landing-page.html` → `index.html` so GitHub Pages serves it by default.
5. Stage all files per the layout above.
6. Write `README.md` per the structure above.
7. Write `.github/workflows/pages.yml`, `LICENSE`, and `.gitignore`.
8. Commit and push (message: `chore: initial showcase content`).
9. Enable GitHub Pages in Settings → Pages → Source: "Deploy from a branch" → `main` / `/ (root)`.

## Verification

1. **Pre-push sanity check** — re-read the three HTML files and confirm no `localhost`, credential, or internal-path strings remain.
2. **Link audit** — `grep -ri "href=" .` in the staged showcase repo; every relative link must resolve within the repo (no `/api/`, `/admin/`, dev-server refs).
3. **After push** — visit `https://github.com/goodwiins/nous` and confirm README renders, screenshots display, logos show.
4. **After Pages is enabled** — visit `https://goodwiinz.github.io/nous/` and verify `index.html` loads with inline styles, logo visible, no broken images.
5. **Screenshot test** — load a few `assets/screenshots/*.png` URLs directly to confirm binaries pushed correctly.

## Scope Guardrails

- **No source code.** Nothing under `backend/src/**`, `frontend/src/**`,
  `tests/**`, or `docker-compose*.yml` is eligible.
- **No infra/config.** Helm charts, ArgoCD manifests, K8s specs — all
  internal. The public repo only contains static marketing content.
- **No customer or dev-user data.** Re-scan screenshots for email
  addresses, names, real API keys. The private repo's admin/demo users
  (`admin@multimodal-rag.com`, `demo@multimodal-rag.com`) appear only in
  dev docs; if they show in screenshots, either accept (they're
  obviously placeholder) or crop.
- **Brand integrity.** Don't modify logos, colors, or typography when
  copying. The private repo is the source of truth.
- **License compliance.** Adding CC BY-NC-ND explicitly forbids
  commercial use — matches the "closed-source project" framing.

## Open Question for Later

Not blocking: do we want to publish the full K-Dense competitive
gap-analysis on the public site? Default plan says no (it's internal
positioning). Can revisit after v1 of the showcase is live.
