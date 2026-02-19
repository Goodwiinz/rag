# Settings Page Design

## Goal

Adapt the existing `/settings` route to a clean, light settings panel that matches the provided references: left-side section navigation and right-side contextual content.

## Scope

- Replace current terminal-themed, multi-module settings UI in `frontend/app/(dashboard)/settings/page.tsx`.
- Keep it as a regular page route, but visually present it as a centered panel over a dimmed background.
- Implement three sections:
  - My Account
  - Agent Usage
  - Connected Apps

## Layout

- Full-height page with muted dark backdrop.
- Centered rounded panel (`max-w` constrained) split into two columns:
  - Left navigation rail (fixed width)
  - Right content area (flexible)
- Mobile behavior:
  - Stack sections vertically (navigation on top, content below)

## Section Content

### My Account

- Primary email display
- Subscription summary text
- "View Plans" action button
- "Log out" outlined/destructive-style button

### Agent Usage

- Plan card with current plan and "Upgrade Plan" CTA
- Monthly credits row with remaining credits
- Lightweight history area with tabs (Usage/Add-On Purchases) and empty-state row

### Connected Apps

- Intro text
- Simple list/empty state for integrations
- Optional connect button placeholder (non-functional)

## Interaction

- Left nav switches content in-place using local state.
- Keep interactions client-side only; no backend calls added.
- Use semantic buttons and clear focus styles.

## Data

- Use `useAuth()` for user email where available.
- Use static placeholder values for plan/credits/history for now, to match screenshot structure without backend changes.

## Constraints

- Do not alter route structure.
- Keep implementation isolated to settings page file.
- Preserve existing project conventions (TypeScript + Tailwind).

## Validation

- Page renders at `/settings`.
- Left nav switching works for all three tabs.
- Layout and spacing visually align with provided references on desktop.
- Mobile viewport stacks properly and remains usable.
