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
  });

  it('removes both "reInit" and "select" listeners on unmount', () => {
    const { unmount } = render(
      <Carousel>
        <CarouselContent />
      </Carousel>
    );

    // Verify listeners were registered
    expect(mockOn).toHaveBeenCalledWith('reInit', expect.any(Function));
    expect(mockOn).toHaveBeenCalledWith('select', expect.any(Function));

    // Unmount — cleanup should call off for both events
    unmount();

    expect(mockOff).toHaveBeenCalledWith('reInit', expect.any(Function));
    expect(mockOff).toHaveBeenCalledWith('select', expect.any(Function));
  });
});
