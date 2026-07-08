/**
 * Single feature gate for the "full assistant-ui alignment" migration
 * (docs plan: piped-snacking-pnueli). While OFF (default), the legacy
 * streaming `ChatBubble` + inline HITL banner render exactly as before.
 * While ON, the in-flight turn streams as a real message in the transcript
 * (P1), tool calls render as declarative Tools() UIs (P2), and HITL approvals
 * are in-band (P4). Kept as the single rollback lever until the legacy path is
 * retired (P5).
 *
 * Module-load-time const (Next inlines `NEXT_PUBLIC_*`); to exercise both
 * paths in tests, `vi.stubEnv` then re-import.
 */
export const AUI_FULL = process.env.NEXT_PUBLIC_AUI_FULL === 'true';
