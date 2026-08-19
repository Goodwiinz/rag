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

/**
 * Split a committed turn's clock into the wait before the first word and the
 * time spent writing it. For an agent turn most of the wall clock is usually
 * retrieval, planning, and tools — "25.8s" alone doesn't say that, and the
 * split is the part a reader can act on.
 *
 * `format` is the caller's own duration formatter so each surface keeps the
 * precision it already uses for the total (ToolStrip prints one decimal, the
 * plan header rounds to whole seconds); only the phrasing and the tooltip live
 * here, so the two can't drift.
 *
 * `suffix` stays null below a second — under that there was no wait worth
 * announcing next to every quick turn — but the breakdown still reaches
 * `title`, so nothing is lost. Both are null/undefined when the turn has no
 * usable reading: `ttftMs` is absent on rows written before the column
 * existed and on turns that streamed no token at all.
 */
export function formatTurnSplit(
  totalMs: number | null | undefined,
  ttftMs: number | null | undefined,
  format: (ms: number) => string | null
): { suffix: string | null; title: string | undefined } {
  const none = { suffix: null, title: undefined };
  if (typeof totalMs !== 'number' || !Number.isFinite(totalMs) || totalMs <= 0) {
    return none;
  }
  // `>= totalMs` also covers the degenerate equal case: a turn whose first
  // token *is* its last leaves nothing to say about writing time.
  if (
    typeof ttftMs !== 'number' ||
    !Number.isFinite(ttftMs) ||
    ttftMs < 0 ||
    ttftMs >= totalMs
  ) {
    return none;
  }
  const first = format(ttftMs);
  const total = format(totalMs);
  const writing = format(totalMs - ttftMs);
  if (!first || !total || !writing) return none;
  return {
    suffix: ttftMs >= 1000 ? `first word ${first}` : null,
    title: `${total} total · ${first} to the first word · ${writing} writing`,
  };
}
