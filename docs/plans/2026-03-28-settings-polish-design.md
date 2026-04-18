# Settings Overview Polish Design

**Date:** 2026-03-28
**Route:** `/settings`
**Design mode:** Premium editorial refinement

## Goal

Refine the new settings overview so it feels more premium and intentional without changing the route structure or turning it into a denser admin console.

## Context

The first pass fixed the product structure:

- `/settings` is now the overview hub
- `/settings/organization` and `/settings/api-keys` exist as valid destinations
- the page reflects NOUS account, workspace, security, and developer-access context

The screenshot review shows the structure is correct, but the page still needs more hierarchy and finish.

## Screenshot Findings

### Working

- overall page shape matches a SaaS settings hub
- status cards are clear and legible
- card grid is structurally sound
- NOUS palette and dark theme are consistent

### Weak

1. The top identity card is visually under-filled for its footprint.
2. The first settings card links back to the same page, which feels broken.
3. The CTA treatment inside cards is too heavy and repetitive.
4. The page needs better rhythm between hero, metrics, and content cards.
5. The bottom-right floating button visually collides with the final card zone.

## Design Direction

Optimize for a more premium, editorial settings page rather than a more operational or more crowded one.

## Approved Changes

### 1. Rebuild the top card into a real hero band

The hero should feel like an account command surface, not a generic info box.

Add:

- avatar-style identity mark
- operator name and email
- role badge
- workspace badge
- last sign-in or session meta
- compact trust chips such as audit active / encrypted / admin access

This should make the top third of the page feel intentional and reduce empty space.

### 2. Make status cards more expressive

Keep the five-card operating-status row, but increase hierarchy with:

- subtle iconography or status dots
- tighter label/value spacing
- optional small secondary indicators where useful

Do not overcomplicate these into dashboards.

### 3. Lighten the settings card actions

Replace the heavy outlined full-width buttons with lighter action rows that feel like navigational affordances.

Preferred direction:

- text link style
- right arrow
- stronger separation between summary copy and action row

The action should support the content, not dominate it.

### 4. Fix the self-linking profile card

`Profile & Preferences` should not navigate to the same route.

Instead:

- make it a jump link to the inline preferences section, or
- make it a non-route interaction such as “Jump to personal controls”

### 5. Add safer bottom spacing

Increase lower-page breathing room so the floating action button does not visually overlap the last visible card area.

## Constraints

- do not add new routes
- do not add backend persistence
- do not rework the full IA
- do not turn the hero into a noisy analytics panel

## Testing Implications

The route-level settings test should be updated to verify:

- richer hero metadata
- profile card action targets the preferences section
- overview behavior still renders as expected

Visual refinement should still preserve semantic headings and accessible link/button names.
