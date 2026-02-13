## 2025-05-15 - Accessible Form Controls in Custom Components
**Learning:** Custom form controls (like div-based switches or radio groups) often lack native accessibility. Using `useId` for linking labels and inputs, and applying correct `role` and `aria-*` attributes is essential. Also, icon-only buttons are a frequent source of missing accessible names.
**Action:** When encountering custom UI components, immediately check for `role`, `aria-label`/`aria-labelledby`, and `tabIndex`. Use `useId` to generate stable IDs for `htmlFor` association.

## 2025-05-23 - Built-in Loading States for Core Components
**Learning:** Developers often forget to handle loading states (disabled, aria-busy, spinner) for buttons during async operations. Baking this into the core Button component via an `isLoading` prop ensures consistent UX and accessibility across the application.
**Action:** When auditing a design system, check if core interactive components (Button, Input) support common states like `isLoading` or `error` natively to reduce implementation burden and errors.
