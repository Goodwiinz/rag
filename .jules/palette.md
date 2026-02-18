## 2025-05-15 - Accessible Form Controls in Custom Components
**Learning:** Custom form controls (like div-based switches or radio groups) often lack native accessibility. Using `useId` for linking labels and inputs, and applying correct `role` and `aria-*` attributes is essential. Also, icon-only buttons are a frequent source of missing accessible names.
**Action:** When encountering custom UI components, immediately check for `role`, `aria-label`/`aria-labelledby`, and `tabIndex`. Use `useId` to generate stable IDs for `htmlFor` association.

## 2025-05-18 - Semantic Buttons vs Interactive Divs
**Learning:** `div`s with `onClick` handlers are prevalent in custom card components but fail keyboard accessibility (tab focus, enter/space activation). Replacing them with `button` elements is the cleanest fix, but requires careful CSS reset (e.g., `text-left`, `w-full`) to maintain layout.
**Action:** Always prefer `<button type="button">` over `<div onClick>` for interactive elements. When refactoring, check for layout shifts and apply `text-left` and `w-full` to match div behavior.
