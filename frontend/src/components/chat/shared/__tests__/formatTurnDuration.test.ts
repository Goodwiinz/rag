import { describe, expect, it } from 'vitest';
import {
  formatStreamingElapsed,
  formatTurnDuration,
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
