## 2025-02-12 - Added ARIA Labels to Icon-Only Buttons
**Learning:** Found a widespread pattern across multiple components where icon-only buttons (like `Button size="icon"`) lacked `aria-label`s, rendering them inaccessible to screen readers. It's crucial to explicitly add `aria-label` to these components since the visual icon does not provide semantic text to assistive technologies.
**Action:** When implementing new interactive elements or icon-only buttons, prioritize adding descriptive `aria-label`s immediately to ensure universal accessibility without relying on visual context alone.

## 2025-02-12 - Updated Test Matchers for Accessibility Changes
**Learning:** When making accessibility improvements such as updating `aria-label`s, associated unit tests (especially those using `screen.getByLabelText(...)` assertions in Jest) may fail if the string changes. This happened with `SearchInterface.tsx` where the label changed from "Toggle filters" to "Toggle search filters".
**Action:** Always run unit tests locally after accessibility changes to catch mismatched `aria-label` strings in tests. Update test assertions correspondingly to match the new, improved labels to maintain test suite stability.
