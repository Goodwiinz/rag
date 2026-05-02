import { render } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Fake Embla API returned by the mock hook
const mockOff = vi.fn();
const mockOn = vi.fn();
const mockApi = {
  on: mockOn,
  off: mockOff,
  canScrollPrev: vi.fn().mockReturnValue(false),
  canScrollNext: vi.fn().mockReturnValue(false),
};

// Stable ref callback — embla-carousel-react returns [refCallback, api]
const mockRefCallback = vi.fn();

vi.mock('embla-carousel-react', () => ({
  default: () => [mockRefCallback, mockApi],
}));

// Import AFTER mocking so the module picks up the mock
import { Carousel, CarouselContent } from '../carousel';

describe('Carousel cleanup', () => {
  beforeEach(() => {
    mockOn.mockClear();
    mockOff.mockClear();
    mockRefCallback.mockClear();
    mockApi.canScrollPrev.mockClear();
    mockApi.canScrollNext.mockClear();
  });

  it('removes both "reInit" and "select" listeners on unmount with the same handler reference', () => {
    const { unmount } = render(
      <Carousel>
        <CarouselContent />
      </Carousel>
    );

    // Capture the exact handler references passed to on()
    const reInitHandler = mockOn.mock.calls.find(([e]) => e === 'reInit')?.[1];
    const selectHandler = mockOn.mock.calls.find(([e]) => e === 'select')?.[1];

    expect(reInitHandler).toBeTypeOf('function');
    expect(selectHandler).toBeTypeOf('function');

    unmount();

    // Cleanup must call off() with the same references — not just any function
    expect(mockOff).toHaveBeenCalledWith('reInit', reInitHandler);
    expect(mockOff).toHaveBeenCalledWith('select', selectHandler);
  });
});
