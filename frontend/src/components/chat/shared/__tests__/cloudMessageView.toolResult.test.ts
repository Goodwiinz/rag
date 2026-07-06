import { describe, expect, it } from 'vitest';
import { mapDbToolExecutions } from '@/components/chat/shared/cloudMessageView';

describe('mapDbToolExecutions result summary', () => {
  it('summarizes an object result persisted by the backend', () => {
    const steps = mapDbToolExecutions([
      {
        tool_name: 'search_documents',
        status: 'success',
        // backend persists parsed JSON — an OBJECT, not a string
        result: { message: 'Found 3 relevant documents' },
      } as never,
    ]);
    expect(steps?.[0].resultSummary).toBe('Found 3 relevant documents');
  });

  it('still handles a string result (legacy rows / error field)', () => {
    const steps = mapDbToolExecutions([
      { tool_name: 't', status: 'success', result: 'plain text' } as never,
    ]);
    expect(steps?.[0].resultSummary).toBe('plain text');
  });

  it('leaves resultSummary undefined when there is no result', () => {
    const steps = mapDbToolExecutions([
      { tool_name: 't', status: 'success' } as never,
    ]);
    expect(steps?.[0].resultSummary).toBeUndefined();
  });
});
