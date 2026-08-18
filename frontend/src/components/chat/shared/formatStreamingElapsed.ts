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

/**
 * Duration of a *finished* turn, for the execution-plan header.
 *
 * Distinct from `formatStreamingElapsed` because the contexts disagree about
 * sub-second readings: while a turn is still running, "0.9s" is noise before
 * the first token. Once it has committed, 0.9s is the answer — and since the
 * plan header is the only place a planned turn shows its duration (ToolStrip
 * stands down to avoid printing it twice), rounding it away would lose the
 * number entirely. Matches ToolStrip's one-decimal style below a second.
 */
export function formatTurnDuration(elapsedMs: number | null): string | null {
  if (elapsedMs === null || !Number.isFinite(elapsedMs) || elapsedMs <= 0) {
    return null;
  }
  if (elapsedMs < 1000) return `${(elapsedMs / 1000).toFixed(1)}s`;
  return formatStreamingElapsed(elapsedMs);
}
