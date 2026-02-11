## 2024-05-23 - Shadcn Select Empty Value Error

**Learning:** Shadcn UI `Select` components throw a runtime error if `SelectItem` values are empty strings (`""`) to represent a cleared or default state.
**Action:** Use explicit sentinel values (e.g., `"any"`, `"default"`) for "all" or "reset" options in `Select` components, and transform these values back to `undefined` or `null` in the `onValueChange` handler.

## 2026-02-04 - [Pagination Accessibility]

**Learning:** Pagination controls with icon-only buttons (like chevron icons) are completely invisible to screen readers without explicit `aria-label`s. Also, using `aria-current="page"` on the active page number provides critical context that `class="..."` styling alone does not.
**Action:** When implementing or modifying navigation components using icons, always verify `aria-label` presence and use standard ARIA states like `aria-current` for active items.

## 2026-02-04 - [Semantic State for Interactive Toggles]

**Learning:** Visual indicators for toggle states (like changing background color on a filter button) are insufficient for screen readers. Users relying on assistive technology need explicit state information.
**Action:** Always pair visual state changes in interactive components with corresponding ARIA attributes, such as `aria-pressed` for toggle buttons and `aria-expanded` for collapsible panels.

## 2026-02-06 - [Button Accessibility & Test Environment]

**Learning:** Shadcn UI `Button` components used as icon-only buttons often lack `aria-label`, requiring explicit addition. Also, the frontend test environment needs `TextEncoder` polyfills for Jest/JSDOM compatibility.
**Action:** Always add `aria-label` to icon-only buttons. Ensure `TextEncoder` and `TextDecoder` are available in `setupTests.ts` when running Jest tests.
