## 2026-02-04 - [Pagination Accessibility]
**Learning:** Pagination controls with icon-only buttons (like chevron icons) are completely invisible to screen readers without explicit `aria-label`s. Also, using `aria-current="page"` on the active page number provides critical context that `class="..."` styling alone does not.
**Action:** When implementing or modifying navigation components using icons, always verify `aria-label` presence and use standard ARIA states like `aria-current` for active items.
