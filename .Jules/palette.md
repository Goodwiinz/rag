
## 2025-03-10 - Add ARIA labels to EntityGraph terminal toolbar buttons
**Learning:** Found multiple icon-only buttons (Zoom In, Zoom Out, Reset, Close details) within the terminal-themed `EntityGraph` visualization overlay that lacked `aria-label`s, preventing screen readers from understanding the control functions despite visual icons being present.
**Action:** Always verify custom toolbar components or overlay cards for interactive visual elements (especially those using the `icon` size variant on generic `Button` components) to ensure they have explicit text fallbacks for accessibility.
