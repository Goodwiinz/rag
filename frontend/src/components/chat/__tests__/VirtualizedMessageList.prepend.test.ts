import { describe, expect, it } from 'vitest';
import { prependScrollDelta } from '@/components/chat/VirtualizedMessageList';

describe('prependScrollDelta', () => {
  it('sums the heights of the prepended rows', () => {
    // Three prepended rows at the default 120px each.
    expect(prependScrollDelta(3, () => 120)).toBe(360);
  });
  it('uses each row’s measured height', () => {
    const sizes = [100, 200, 50];
    expect(prependScrollDelta(3, (i) => sizes[i])).toBe(350);
  });
  it('is zero when nothing was prepended', () => {
    expect(prependScrollDelta(0, () => 120)).toBe(0);
  });
});
