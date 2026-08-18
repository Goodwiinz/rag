/**
 * Elapsed run time for a turn: "47s", "2m 05s". Sub-second readings are
 * noise while the first token is still plausibly imminent.
 *
 * Shared by AuiMessage's pre-first-token pill and ChatInlinePlan's committed
 * "took …" header — living here (rather than in either component) avoids an
 * import cycle, since AuiMessage imports ChatInlinePlan.
 */
export function formatStreamingElapsed(
  elapsedMs: number | null
): string | null {
  if (elapsedMs === null || !Number.isFinite(elapsedMs) || elapsedMs < 1000) {
    return null;
  }
  const totalSeconds = Math.floor(elapsedMs / 1000);
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${String(seconds).padStart(2, '0')}s`;
}
