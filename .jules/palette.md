## 2025-05-15 - Accessible Form Controls in Custom Components
**Learning:** Custom form controls (like div-based switches or radio groups) often lack native accessibility. Using `useId` for linking labels and inputs, and applying correct `role` and `aria-*` attributes is essential. Also, icon-only buttons are a frequent source of missing accessible names.
**Action:** When encountering custom UI components, immediately check for `role`, `aria-label`/`aria-labelledby`, and `tabIndex`. Use `useId` to generate stable IDs for `htmlFor` association.

## 2025-05-18 - Semantic Buttons vs Interactive Divs
**Learning:** `div`s with `onClick` handlers are prevalent in custom card components but fail keyboard accessibility (tab focus, enter/space activation). Replacing them with `button` elements is the cleanest fix, but requires careful CSS reset (e.g., `text-left`, `w-full`) to maintain layout.
**Action:** Always prefer `<button type="button">` over `<div onClick>` for interactive elements. When refactoring, check for layout shifts and apply `text-left` and `w-full` to match div behavior.

## 2025-05-20 - Roving Tabindex for Custom Radio Groups
**Learning:** Custom "radio button" groups implemented as a set of buttons often lack arrow key navigation support, forcing keyboard users to tab through every option. The Roving Tabindex pattern (`tabIndex={selected ? 0 : -1}`) combined with arrow key handling (`onKeyDown`) provides a much better experience.
**Action:** When identifying custom selection groups (like style selectors), implement Roving Tabindex to allow single-tab entry and arrow key navigation within the group.
