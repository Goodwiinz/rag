# Palette Journal

## 2025-03-05 - Adding ARIA labels to icon-only Buttons
**Learning:** Found that multiple components use icon-only buttons (e.g., `<Button size="icon">`) but omit an `aria-label` entirely. This breaks screen readers. This pattern is easy to miss when `size="icon"` is used.
**Action:** Add explicit `aria-label` attributes to components wrapping or using `size="icon"` buttons.
