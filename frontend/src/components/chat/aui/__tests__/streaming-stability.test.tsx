import { describe, expect, it } from 'vitest';
import React, { Profiler, useState } from 'react';
import { act, render } from '@testing-library/react';
import { AuiToolParts } from '../AuiToolParts';
import type { ActivityStep } from '@/components/chat/shared/cloudMessageView';

/**
 * Streaming render contract: token updates re-render the parent (text
 * changes), but the tool UI must not re-render as long as the steps array
 * reference is unchanged — streamingSteps only gets a new reference on
 * tool_start/tool_end, never per token.
 */
describe('streaming render stability', () => {
  it('tool parts do not re-render across 50 simulated token updates', () => {
    const steps: ActivityStep[] = [
      { tool: 'search_arxiv', label: 'Searching arXiv', status: 'running' },
    ];
    let renders = 0;
    let pushToken: (s: string) => void = () => undefined;

    function Harness(): React.ReactElement {
      const [, setToken] = useState('');
      pushToken = (s) => setToken(s);
      return (
        <Profiler id="tool-parts" onRender={() => renders++}>
          <AuiToolParts messageId="m1" steps={steps} isStreaming />
        </Profiler>
      );
    }

    render(<Harness />);
    const rendersAfterMount = renders;

    act(() => {
      for (let i = 0; i < 50; i++) pushToken(`token-${i}`);
    });

    // ToolFallback's internal store subscription settles with one async
    // re-render after mount; the guard is that renders don't scale with
    // token count (a per-token leak would add ~50 here).
    expect(renders - rendersAfterMount).toBeLessThanOrEqual(1);
  });

  it('a new steps reference (tool_end) does re-render the tool parts', () => {
    let renders = 0;
    let setSteps: (s: ActivityStep[]) => void = () => undefined;
    const running: ActivityStep[] = [
      { tool: 'search_arxiv', label: 'Searching arXiv', status: 'running' },
    ];

    function Harness(): React.ReactElement {
      const [steps, set] = useState(running);
      setSteps = set;
      return (
        <Profiler id="tool-parts" onRender={() => renders++}>
          <AuiToolParts messageId="m1" steps={steps} isStreaming />
        </Profiler>
      );
    }

    render(<Harness />);
    const before = renders;
    act(() => {
      setSteps([
        {
          tool: 'search_arxiv',
          label: 'Searching arXiv',
          status: 'done',
          durationMs: 900,
        },
      ]);
    });
    expect(renders).toBeGreaterThan(before);
  });
});
