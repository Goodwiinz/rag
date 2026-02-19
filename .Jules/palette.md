## 2025-05-20 - Interactive Divs vs Buttons
**Learning:** I found an `EnhancedAssistantCard` implemented as a `div` with `onClick`, making it inaccessible to keyboard users and screen readers. This is a common pattern in custom UI components where visual design is prioritized over semantics.
**Action:** Always check interactive cards for semantic HTML. Convert `div`s with `onClick` to `<button type="button">` and ensure proper styling (e.g., `w-full text-left`) to maintain visual fidelity while gaining accessibility benefits for free.
