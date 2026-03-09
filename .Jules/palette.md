## 2026-03-09 - Added ARIA Labels to EntityGraph Buttons
**Learning:** Found that the `<Button size="icon">` component in `EntityGraph.tsx` only contained SVG icons (ZoomIn, ZoomOut, RefreshCw, and Close) and was missing `aria-label` attributes, which makes them inaccessible to screen readers since they have no programmatic name. This is a common pattern to look out for in the codebase.
**Action:** When creating or modifying icon-only buttons, always explicitly add `aria-label` or `title` attributes (or ensure the `Button` component enforces it if applicable).
