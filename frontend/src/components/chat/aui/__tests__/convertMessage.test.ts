import { describe, expect, it } from 'vitest';

import type { ActivityStep, ChatPageMessage } from '../../shared/cloudMessageView';
import { convertMessage, toToolCallParts } from '../convertMessage';

function makeMessage(overrides: Partial<ChatPageMessage> = {}): ChatPageMessage {
  return {
    id: 'm1',
    role: 'assistant',
    content: 'Hello there',
    timestamp: 1720000000000,
    ...overrides,
  };
}

describe('convertMessage', () => {
  it('converts a plain assistant message to a single text part', () => {
    const result = convertMessage(makeMessage());

    expect(result.id).toBe('m1');
    expect(result.role).toBe('assistant');
    expect(result.createdAt).toEqual(new Date(1720000000000));
    expect(result.content).toEqual([{ type: 'text', text: 'Hello there' }]);
  });

  it('maps toolExecutions to tool-call parts before the text part', () => {
    const steps: ActivityStep[] = [
      {
        tool: 'search_documents',
        label: 'Searching documents',
        status: 'done',
        argsSummary: 'query: transformers',
        resultSummary: 'Found 3 documents',
      },
      {
        tool: 'ingest_arxiv',
        label: 'Ingesting paper',
        status: 'error',
        argsSummary: 'id: 2401.00001',
        resultSummary: 'Timed out',
      },
    ];
    const result = convertMessage(makeMessage({ toolExecutions: steps }));
    const content = result.content as Array<Record<string, unknown>>;

    expect(content).toHaveLength(3);
    expect(content[0]).toEqual({
      type: 'tool-call',
      toolCallId: 'm1-tool-0',
      toolName: 'search_documents',
      args: {},
      argsText: 'query: transformers',
      result: 'Found 3 documents',
    });
    expect(content[1]).toEqual({
      type: 'tool-call',
      toolCallId: 'm1-tool-1',
      toolName: 'ingest_arxiv',
      args: {},
      argsText: 'id: 2401.00001',
      result: 'Timed out',
      isError: true,
    });
    expect(content[2]).toEqual({ type: 'text', text: 'Hello there' });
  });

  it('emits no result and no isError for a running step', () => {
    const steps: ActivityStep[] = [
      { tool: 'search_arxiv', label: 'Searching arXiv', status: 'running' },
    ];
    const [part] = toToolCallParts('m1', steps);

    expect(part).not.toHaveProperty('result');
    expect(part).not.toHaveProperty('isError');
  });

  it('defaults args to {} and argsText to empty string when argsSummary is missing', () => {
    const steps: ActivityStep[] = [
      { tool: 'list_projects', label: 'Listing projects', status: 'done' },
    ];
    const [part] = toToolCallParts('m1', steps);

    expect(part.args).toEqual({});
    expect(part.argsText).toBe('');
  });

  it('returns referentially stable parts for the same steps array reference', () => {
    const steps: ActivityStep[] = [
      { tool: 'search_documents', label: 'Searching', status: 'running' },
    ];

    expect(toToolCallParts('m1', steps)).toBe(toToolCallParts('m1', steps));
  });
});
