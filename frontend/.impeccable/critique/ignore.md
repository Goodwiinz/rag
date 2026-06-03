# Impeccable critique — ignore list

Findings confirmed as false positives. Drop these silently in critique runs.

## border-accent-on-rounded — loading spinners (not accent borders)

`border-b-2` combined with `animate-spin rounded-full` is the standard
Tailwind spinner construction, not a side-accent border on a card. Ignore
`border-accent-on-rounded` wherever the same element also has `animate-spin`.

Known locations:

- src/components/evaluation/EvaluationManagement.tsx:323
- src/components/graph/EntityDetailsPanel.tsx:83
- src/components/optimized/OptimizedDocumentList.tsx:180
- src/components/preview/MultimodalViewer.tsx:441
- src/page-components/Dashboard.tsx
- src/page-components/Login.tsx
- src/page-components/Register.tsx
- src/page-components/auth/LoginPage.tsx
- src/providers/WebSocketProvider.tsx
- src/router/index.tsx

## side-tab — CSS triangle caret (not a side stripe)

src/components/chat/RAGToggle.tsx:159 uses `border-l-4 border-r-4 border-t-4
border-transparent` to draw a tooltip arrow (the classic CSS-triangle trick),
not a colored side stripe. Ignore.
