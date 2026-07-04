import { describe, expect, it } from 'vitest';
import {
  deriveStepStatus,
  formatArgsHint,
  mapPlanToTasks,
} from '../planMapping';
import type { PlanStep, ToolExecution } from '@/types/agent-chat';

function makeStep(overrides: Partial<PlanStep> = {}): PlanStep {
  return {
    step: 1,
    description: 'Search arXiv',
    tool: 'search_arxiv',
    args_hint: {},
    depends_on: [],
    ...overrides,
  };
}

function makeExec(overrides: Partial<ToolExecution> = {}): ToolExecution {
  return {
    id: 'exec-1',
    toolName: 'search_arxiv',
    toolDisplayName: 'Search arXiv',
    args: {},
    status: 'completed',
    ...overrides,
  };
}

describe('deriveStepStatus', () => {
  it('returns pending when no matching executions', () => {
    expect(deriveStepStatus(makeStep(), [])).toBe('pending');
  });

  it('returns failed when any matching execution failed', () => {
    const execs = [
      makeExec({ status: 'completed' }),
      makeExec({ status: 'failed' }),
    ];
    expect(deriveStepStatus(makeStep(), execs)).toBe('failed');
  });

  it('returns in-progress when any matching execution is running (and none failed)', () => {
    const execs = [
      makeExec({ status: 'completed' }),
      makeExec({ status: 'running' }),
    ];
    expect(deriveStepStatus(makeStep(), execs)).toBe('in-progress');
  });

  it('returns completed when all matching executions completed', () => {
    const execs = [makeExec({ status: 'completed' })];
    expect(deriveStepStatus(makeStep(), execs)).toBe('completed');
  });

  it('prioritizes failed over running and completed', () => {
    const execs = [
      makeExec({ status: 'completed' }),
      makeExec({ status: 'running' }),
      makeExec({ status: 'failed' }),
    ];
    expect(deriveStepStatus(makeStep(), execs)).toBe('failed');
  });

  it('ignores executions for other tools', () => {
    const execs = [makeExec({ toolName: 'other_tool', status: 'failed' })];
    expect(deriveStepStatus(makeStep(), execs)).toBe('pending');
  });
});

describe('formatArgsHint', () => {
  it('returns empty string for empty object', () => {
    expect(formatArgsHint({})).toBe('');
  });

  it('formats string values without JSON quoting', () => {
    expect(formatArgsHint({ query: 'transformers' })).toBe(
      'query: transformers'
    );
  });

  it('JSON-stringifies non-string values', () => {
    expect(formatArgsHint({ limit: 5 })).toBe('limit: 5');
  });

  it('joins multiple entries with a middot separator', () => {
    expect(formatArgsHint({ query: 'x', limit: 5 })).toBe(
      'query: x · limit: 5'
    );
  });
});

describe('mapPlanToTasks', () => {
  it('maps step fields onto a flat task list', () => {
    const steps = [
      makeStep({
        step: 1,
        description: 'Search arXiv',
        tool: 'search_arxiv',
        args_hint: { query: 'x' },
        depends_on: [],
      }),
      makeStep({
        step: 2,
        description: 'Ingest paper',
        tool: 'ingest_document',
        args_hint: {},
        depends_on: [1],
      }),
    ];
    const execs = [makeExec({ status: 'completed' })];

    const tasks = mapPlanToTasks(steps, execs);

    expect(tasks).toHaveLength(2);
    expect(tasks[0]).toMatchObject({
      id: '1',
      title: 'Search arXiv',
      description: 'query: x',
      status: 'completed',
      dependencies: [],
      subtasks: [],
      tools: ['search_arxiv'],
    });
    expect(tasks[1]).toMatchObject({
      id: '2',
      title: 'Ingest paper',
      status: 'pending',
      dependencies: ['1'],
      tools: ['ingest_document'],
    });
  });

  it('omits tools array entry when step has no tool', () => {
    const tasks = mapPlanToTasks([makeStep({ tool: '' })], []);
    expect(tasks[0].tools).toEqual([]);
  });
});
