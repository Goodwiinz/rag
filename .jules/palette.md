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

## 2026-02-09 - [Terminal UI Search Patterns]

**Learning:** In "terminal-style" or power-user interfaces, users expect keyboard-first navigation (like `/` to focus search) and quick reset capabilities. A search input without a clear button forces users to manually backspace, breaking the flow.
**Action:** Always implement a clear button and global keyboard shortcut (checking for `activeElement` to avoid conflicts) for primary search inputs in data-heavy applications.

## 2026-02-10 - [Zip Bomb Detection Div-by-Zero]

**Learning:** When analyzing ZIP files for zip bomb detection, a file entry can have `compress_size == 0` (e.g., stored files with no compression). Dividing `file_size / compressed_size` without checking causes a `ZeroDivisionError`.
**Action:** Always guard division with checks on both numerator and denominator when computing compression ratios.

## 2026-02-10 - [Sidebar Toggle Accessibility]

**Learning:** Legacy UI components (like the sidebar toggle in `Sidebar.tsx`) often lack semantic HTML and ARIA attributes, relying solely on `div`s and `onClick` handlers. Even if components seem unused in the main flow, they may be imported elsewhere.
**Action:** When auditing for accessibility, check imported but potentially "legacy" components for missing semantic structure (buttons vs divs) and ensure they are testable.

## 2026-02-10 - [Accessibility: Modal Standardization]

**Learning:** Custom-built modal dialogs often lack critical accessibility features like focus trapping and screen reader support. Replacing them with standardized components (like Shadcn UI Dialog) instantly solves these issues while maintaining visual consistency through custom styling.
**Action:** Always prioritize using library-provided Dialog components over custom `div` overlays for modal interfaces.
