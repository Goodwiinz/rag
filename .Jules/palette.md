## 2024-05-24 - Search Input Keyboard Shortcut Hint
**Learning:** Users often miss global keyboard shortcuts like `/` for search unless there's a visual cue directly on the element.
**Action:** When implementing global shortcuts for inputs, add a visual "badge" (e.g., a small `/` or `Cmd+K` icon) positioned absolutely within the input that is hidden when the user starts typing. Ensure it is hidden from screen readers (`aria-hidden="true"`) if the shortcut is handled via global event listeners to avoid confusion with the input's actual value or label.
