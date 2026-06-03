---
target: /chat (live)
total_score: 31
p0_count: 0
p1_count: 0
timestamp: 2026-05-28T15-32-30Z
slug: localhost-chat
---
#### /chat post-fix (live-verified)

| # | Heuristic | Before | After | Note |
|---|-----------|--------|-------|------|
| 1 | System Status | 2 | 3 | 15s init watchdog -> recoverable error instead of infinite "Initializing…" (backend 500s still upstream) |
| 2 | Match Real World | 2 | 3 | Status labels sentence-case Inter ("Connection error", "Loading messages…") instead of uppercase mono |
| 3 | User Control | 3 | 3 | unchanged |
| 4 | Consistency | 2 | 3 | Main surface unified to --nous-* tokens; command palette de-terminal'd |
| 5 | Error Prevention | 3 | 3 | HITL approve/deny intact |
| 6 | Recognition | 3 | 3 | unchanged |
| 7 | Flexibility/Efficiency | 4 | 4 | unchanged |
| 8 | Aesthetic/Minimalist | 2 | 3 | Terminal-window chrome, star-field/grid bg, glassmorphism, mono labels removed from main surface |
| 9 | Error Recovery | 3 | 4 | Watchdog + visible retry path |
| 10 | Help/Docs | 2 | 2 | unchanged (deferred) |
| **Total** | | **25** | **31** | |

#### What changed (live-verified)
- **De-costume**: command palette rebuilt on `--nous-*` (was `terminal-window` + `--phosphor-green` + all-mono); `star-field terminal-grid noise-texture` layout bg removed; `font-mono` demoted to code/kbd only on the main surface; "CONNECTION ERROR"/"RETRY CONNECTION"/"LOADING MESSAGES…" → sentence case Inter; HITL buttons de-uppercased. Live audit: zero `terminal-window`/`star-field`/`nous-glass`/`backdrop-blur` classes remain on /chat.
- **Init resilience**: 15s watchdog in `useChatSession` flips a hung init to a visible recoverable error; cleared on settle/unmount.
- **Skeletons**: message-loading spinner replaced with skeleton message rows (`Skeleton`), `aria-busy`.
- **De-glass**: `nous-glass`/`nous-composer-glow`/`shadow-black/50` on ChatHeader, mobile drawer, SearchComposer → solid `--nous-bg-*` + hairline border + focus-within ring; mobile drawer spring → ease-out tween; blur scrims → `--nous-erebus/50`.
- **a11y**: unnamed context-rail select button got `aria-label` + `aria-hidden` icon. Live audit: 0 unnamed buttons (was 1).

#### Deferred (flagged, not done)
- **App-wide costume migration**: `--terminal-*` / `--phosphor-green` are aliased to NOUS gold (so visually warm, not green) but the legacy var NAMES + costume classes span ~59 files; the /dashboard still shows heavy "NEURAL / SYNTHETIC INSIGHTS / EXECUTE NEURAL SESSION" copy. Separate migration.
- **Rail polish**: ChatSidebar metadata + ContextRail labels still use mono chips + uppercase tracked labels ("WORKING FOLDERS", "DETACHED CHAT"). Lower severity; not the main column.
- **Backend 500s**: dashboard-overview 500s are upstream; only frontend resilience was in scope.
