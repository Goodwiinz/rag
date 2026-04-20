/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { AgentActivityPanel } from '../AgentActivityPanel';
import { useAgentActivityStore } from '@/stores/agentActivityStore';

describe('AgentActivityPanel', () => {
  beforeEach(() => {
    useAgentActivityStore.setState({ runs: {}, currentThreadId: null });
  });

  it('returns null when no run exists for the thread', () => {
    const { container } = render(<AgentActivityPanel threadId="t-missing" />);
    expect(container.firstChild).toBeNull();
  });

  it('returns null when threadId is null', () => {
    const { container } = render(<AgentActivityPanel threadId={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders name, task, and step labels during running state', () => {
    const store = useAgentActivityStore.getState();
    store.startRun('t1', 'Literature synth', 'Reviewing Mamba-2');
    store.pushToolStart('t1', 'arxiv_search');
    store.pushToolEnd('t1', 'arxiv_search', true);
    store.pushToolStart('t1', 'create_draft');

    render(<AgentActivityPanel threadId="t1" />);

    expect(screen.getByText('Literature synth')).toBeInTheDocument();
    expect(screen.getByText('Reviewing Mamba-2')).toBeInTheDocument();
    expect(screen.getByText('Search arXiv')).toBeInTheDocument();
    expect(screen.getByText('Draft synthesis')).toBeInTheDocument();
  });

  it('renders frozen list when run has finished', () => {
    const store = useAgentActivityStore.getState();
    store.startRun('t1', 'NOUS Agent', 'done task');
    store.pushToolStart('t1', 'arxiv_search');
    store.pushToolEnd('t1', 'arxiv_search', true);
    store.finishRun('t1', 'done');

    render(<AgentActivityPanel threadId="t1" />);

    expect(screen.getByText('Search arXiv')).toBeInTheDocument();
  });

  it('renders errored steps (maps to done visually in v1)', () => {
    const store = useAgentActivityStore.getState();
    store.startRun('t1', 'NOUS Agent', 'task');
    store.pushToolStart('t1', 'arxiv_search');
    store.pushToolEnd('t1', 'arxiv_search', false);

    render(<AgentActivityPanel threadId="t1" />);

    expect(screen.getByText('Search arXiv')).toBeInTheDocument();
  });
});
