## 2024-05-08 - Icon-only Button Accessibility
**Learning:** Raw `<button>` elements for icon-only actions often lack tooltips and consistent accessibility attributes, leading to duplicate `aria-label`s or screen reader unfriendliness. Using the dedicated `IconButton` component enforces an `aria-label` (via the `label` prop) and automatically provides an informative tooltip on hover.
**Action:** Always prefer `IconButton` (from `@/components/ui/icon-button`) over raw HTML `<button>`s when adding or modifying icon-only actions to ensure built-in tooltips and guaranteed screen reader accessibility.
## 2026-05-11 - Citation Graph Accessibility
**Learning:** Replaced cryptic ASCII characters (+, -, [], R) in raw button tags with standard Lucide React icons wrapped in the app's native IconButton component within the CitationGraph controls. This significantly improves visual clarity, keyboard focus styling, and screen-reader accessibility via built-in aria-label and Tooltip handling.
**Action:** Always scan for generic `<button>` implementations in rich interactive components like graphs or data tables and replace them with standard design system components like `IconButton` that enforce accessibility.
## 2026-05-14 - [Add tablist accessibility pattern]
**Learning:** Interactive tabs built from native `<button>`s require explicit ARIA roles (`role="tablist"`, `role="tab"`) and state indicators (`aria-selected`) to be correctly announced by screen readers.
**Action:** When creating custom tab navigations, always implement the standard WAI-ARIA tab pattern rather than relying on generic button elements.
## 2024-05-18 - Stylized Button Accessibility
**Learning:** Custom semantic buttons with unconventional or stylized visible text (e.g., 'TRANSMIT' or 'HALT') fail to provide clear context for screen reader users relying on standard labels.
**Action:** Always ensure explicitly declared `aria-label`s (like 'Send message' or 'Stop generation') are applied for screen reader compatibility, rather than relying solely on `title` attributes or the visible text.
## 2025-05-14 - Search Interface Focus Accessibility
**Learning:** Interactive generic components built using native HTML buttons lack default distinct keyboard focus states outside of standard buttons. Screen reader and keyboard navigation usability heavily degraded when complex forms lack proper tablist ARIA tagging.
**Action:** Apply `focus-visible:ring-2 focus-visible:outline-none` utilities for clean keyboard tracking, and formally tag `<nav>` with `role="tablist"` containing child `role="tab"` items linked with `aria-selected` when replicating tabular navigation.
