import { fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useTheme } from 'next-themes';

import { InteractiveKnowledgeGraph } from '../InteractiveKnowledgeGraph';

vi.mock('next-themes', () => ({
  useTheme: vi.fn(),
}));

const mockedUseTheme = vi.mocked(useTheme);

type CanvasCall = unknown[];

const createCanvasContext = () => {
  const gradient = {
    addColorStop: vi.fn(),
  };

  return {
    clearRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    createRadialGradient: vi.fn(() => gradient),
    strokeStyle: '',
    fillStyle: '',
    lineWidth: 0,
  };
};

describe('InteractiveKnowledgeGraph', () => {
  let context: ReturnType<typeof createCanvasContext>;
  let animationCallbacks: FrameRequestCallback[];
  let getContextSpy: ReturnType<typeof vi.spyOn>;
  let getBoundingClientRectSpy: ReturnType<typeof vi.spyOn>;
  let randomSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockedUseTheme.mockReturnValue({
      resolvedTheme: 'dark',
    } as ReturnType<typeof useTheme>);

    context = createCanvasContext();
    animationCallbacks = [];

    getContextSpy = vi
      .spyOn(HTMLCanvasElement.prototype, 'getContext')
      .mockReturnValue(context as unknown as CanvasRenderingContext2D);
    getBoundingClientRectSpy = vi
      .spyOn(HTMLCanvasElement.prototype, 'getBoundingClientRect')
      .mockReturnValue({
        x: 0,
        y: 0,
        width: 500,
        height: 128,
        top: 0,
        right: 500,
        bottom: 128,
        left: 0,
        toJSON: () => {},
      } as DOMRect);
    randomSpy = vi.spyOn(Math, 'random').mockReturnValue(0);

    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn((callback: FrameRequestCallback) => {
        animationCallbacks.push(callback);
        return animationCallbacks.length;
      })
    );
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  const runNextAnimationFrame = () => {
    const callback = animationCallbacks.shift();
    expect(callback).toBeDefined();
    callback?.(16);
  };

  const expectFiniteCanvasCalls = (calls: CanvasCall[]) => {
    for (const call of calls) {
      for (const value of call) {
        if (typeof value === 'number') {
          expect(Number.isFinite(value)).toBe(true);
        }
      }
    }
  };

  it('draws cursor links after mouse movement without restarting the animation loop', () => {
    const { container } = render(<InteractiveKnowledgeGraph />);
    const canvas = container.querySelector('canvas');

    expect(canvas).toBeInTheDocument();
    expect(getContextSpy).toHaveBeenCalledWith('2d');
    expect(requestAnimationFrame).toHaveBeenCalledTimes(1);

    context.lineTo.mockClear();
    fireEvent.mouseMove(canvas!, { clientX: 10, clientY: 10 });
    runNextAnimationFrame();

    expect(context.lineTo).toHaveBeenCalledWith(10, 10);
    expect(requestAnimationFrame).toHaveBeenCalledTimes(2);
  });

  it('keeps node drawing finite when the cursor exactly overlaps a node', () => {
    const { container } = render(<InteractiveKnowledgeGraph />);
    const canvas = container.querySelector('canvas');

    fireEvent.mouseMove(canvas!, { clientX: 0, clientY: 0 });
    runNextAnimationFrame();

    expectFiniteCanvasCalls(context.moveTo.mock.calls);
    expectFiniteCanvasCalls(context.lineTo.mock.calls);
    expectFiniteCanvasCalls(context.arc.mock.calls);
    expectFiniteCanvasCalls(context.createRadialGradient.mock.calls);
  });

  it('removes browser listeners and cancels the pending frame on unmount', () => {
    const addWindowListenerSpy = vi.spyOn(window, 'addEventListener');
    const removeWindowListenerSpy = vi.spyOn(window, 'removeEventListener');
    const addCanvasListenerSpy = vi.spyOn(
      HTMLCanvasElement.prototype,
      'addEventListener'
    );
    const removeCanvasListenerSpy = vi.spyOn(
      HTMLCanvasElement.prototype,
      'removeEventListener'
    );

    const { unmount } = render(<InteractiveKnowledgeGraph />);

    expect(addWindowListenerSpy).toHaveBeenCalledWith(
      'resize',
      expect.any(Function)
    );
    expect(addCanvasListenerSpy).toHaveBeenCalledWith(
      'mousemove',
      expect.any(Function)
    );
    expect(addCanvasListenerSpy).toHaveBeenCalledWith(
      'mouseleave',
      expect.any(Function)
    );

    unmount();

    expect(removeWindowListenerSpy).toHaveBeenCalledWith(
      'resize',
      expect.any(Function)
    );
    expect(removeCanvasListenerSpy).toHaveBeenCalledWith(
      'mousemove',
      expect.any(Function)
    );
    expect(removeCanvasListenerSpy).toHaveBeenCalledWith(
      'mouseleave',
      expect.any(Function)
    );
    expect(cancelAnimationFrame).toHaveBeenCalledWith(1);
  });
});
