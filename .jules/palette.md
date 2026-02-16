## 2025-05-15 - Accessible Form Controls in Custom Components
**Learning:** Custom form controls (like div-based switches or radio groups) often lack native accessibility. Using `useId` for linking labels and inputs, and applying correct `role` and `aria-*` attributes is essential. Also, icon-only buttons are a frequent source of missing accessible names.
**Action:** When encountering custom UI components, immediately check for `role`, `aria-label`/`aria-labelledby`, and `tabIndex`. Use `useId` to generate stable IDs for `htmlFor` association.

## 2026-02-16 - Consistent Loading States in Buttons
**Learning:** Implementing `isLoading` logic within the base `Button` component ensures consistent loading feedback across the application and prevents ad-hoc, inaccessible implementations. It also handles accessibility concerns like `disabled` state and screen reader announcements automatically.
**Action:** Enhance base UI components with built-in state handling (like loading) to enforce consistent UX patterns and reduce boilerplate code for consumers.
