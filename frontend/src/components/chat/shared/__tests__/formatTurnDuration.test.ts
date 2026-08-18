import { describe, expect, it } from 'vitest';
import {
  formatStreamingElapsed,
  formatTurnDuration,
  formatTurnSplit,
} from '../formatStreamingElapsed';

describe('formatTurnDuration', () => {
  it('keeps sub-second durations that the streaming formatter drops', () => {
    // A planned turn shows its duration ONLY in the plan header — ToolStrip
    // stands down so the number is not printed twice. Rounding sub-second
    // readings away would therefore lose it entirely: a 900ms turn would
    // report no duration anywhere.
    expect(formatStreamingElapsed(900)).toBeNull();
    expect(formatTurnDuration(900)).toBe('0.9s');
  });

  it('matches the streaming formatter from one second up', () => {
    for (const ms of [1000, 2300, 47_000, 125_000]) {
      expect(formatTurnDuration(ms)).toBe(formatStreamingElapsed(ms));
    }
  });

  it('reports nothing for a turn with no measured duration', () => {
    expect(formatTurnDuration(0)).toBeNull();
    expect(formatTurnDuration(null)).toBeNull();
    expect(formatTurnDuration(Number.NaN)).toBeNull();
  });
});

describe('formatTurnSplit', () => {
  const oneDecimal = (ms: number): string => `${(ms / 1000).toFixed(1)}s`;

  it('splits the clock into the wait and the writing', () => {
    const { suffix, title } = formatTurnSplit(25_800, 24_100, oneDecimal);
    expect(suffix).toBe('first word 24.1s');
    expect(title).toBe('25.8s total · 24.1s to the first word · 1.7s writing');
  });

  it('keeps the breakdown in the tooltip but hides it below a second', () => {
    // A turn that started answering immediately has no wait worth printing
    // next to it — but the numbers are still there on hover.
    const { suffix, title } = formatTurnSplit(2000, 400, oneDecimal);
    expect(suffix).toBeNull();
    expect(title).toBe('2.0s total · 0.4s to the first word · 1.6s writing');
  });

  it('reports nothing when there is no first-token reading', () => {
    // Rows written before chat_messages.ttft_ms existed, and turns that
    // streamed no token at all (error before generation, stop during tools).
    for (const ttft of [undefined, null]) {
      expect(formatTurnSplit(25_800, ttft, oneDecimal)).toEqual({
        suffix: null,
        title: undefined,
      });
    }
  });

  it('reports nothing when the reading cannot be a subset of the total', () => {
    // ttft >= total would render a zero or negative writing time. Both clocks
    // share an origin so this should not happen; if a legacy row or a clock
    // skew produces it, the strip says nothing rather than something false.
    for (const [total, ttft] of [
      [25_800, 25_800],
      [25_800, 30_000],
      [25_800, -1],
      [0, 0],
    ]) {
      expect(formatTurnSplit(total, ttft, oneDecimal).suffix).toBeNull();
    }
  });

  it('uses the caller-supplied formatter so each surface keeps its precision', () => {
    // The plan header rounds to whole seconds; the strip prints one decimal.
    const { suffix } = formatTurnSplit(25_800, 24_100, (ms) =>
      formatTurnDuration(ms)
    );
    expect(suffix).toBe('first word 24s');
  });
});
