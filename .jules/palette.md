## 2024-05-23 - Shadcn Select Empty Value Error
**Learning:** Shadcn UI `Select` components throw a runtime error if `SelectItem` values are empty strings (`""`) to represent a cleared or default state.
**Action:** Use explicit sentinel values (e.g., `"any"`, `"default"`) for "all" or "reset" options in `Select` components, and transform these values back to `undefined` or `null` in the `onValueChange` handler.
