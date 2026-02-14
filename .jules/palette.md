## 2025-05-15 - Accessible Form Controls in Custom Components
**Learning:** Custom form controls (like div-based switches or radio groups) often lack native accessibility. Using `useId` for linking labels and inputs, and applying correct `role` and `aria-*` attributes is essential. Also, icon-only buttons are a frequent source of missing accessible names.
**Action:** When encountering custom UI components, immediately check for `role`, `aria-label`/`aria-labelledby`, and `tabIndex`. Use `useId` to generate stable IDs for `htmlFor` association.

## 2025-05-23 - Accessibility: Skip-to-Content Link
**Learning:** Even modern frameworks like Next.js don't automatically provide a "Skip to Content" mechanism, which is a critical WCAG requirement (2.4.1). Manually managing `id="main-content"` across different layouts is necessary.
**Action:** When creating new layouts, always include a `<main id="main-content">` wrapper and ensure the root layout has a `SkipLink` component.
