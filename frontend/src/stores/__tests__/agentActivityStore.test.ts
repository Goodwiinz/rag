import { useAgentActivityStore } from '../agentActivityStore';

describe('agentActivityStore', () => {
  beforeEach(() => {
    useAgentActivityStore.setState({ runs: {}, currentThreadId: null });
  });

  const getRun = (threadId: string) =>
    useAgentActivityStore.getState().runs[threadId];

  it('startRun initializes a running run with empty steps', () => {
    useAgentActivityStore
      .getState()
      .startRun('t1', 'Literature synth', 'Reviewing Mamba-2');

    const run = getRun('t1');
    expect(run.state).toBe('running');
    expect(run.name).toBe('Literature synth');
    expect(run.task).toBe('Reviewing Mamba-2');
    expect(run.steps).toEqual([]);
  });

  it('pushToolStart appends an active step with a mapped label', () => {
    const { startRun, pushToolStart } = useAgentActivityStore.getState();
    startRun('t1', 'NOUS Agent', 'task');
    pushToolStart('t1', 'arxiv_search');

    const steps = getRun('t1').steps;
    expect(steps).toHaveLength(1);
    expect(steps[0].tool).toBe('arxiv_search');
    expect(steps[0].status).toBe('active');
    expect(steps[0].label).toBe('Search arXiv');
  });

  it('duplicate pushToolStart for same tool is de-duped while active', () => {
    const { startRun, pushToolStart } = useAgentActivityStore.getState();
    startRun('t1', 'NOUS Agent', 'task');
    pushToolStart('t1', 'arxiv_search');
    pushToolStart('t1', 'arxiv_search');
    expect(getRun('t1').steps).toHaveLength(1);
  });

  it('pushToolEnd flips matching active step to done', () => {
    const { startRun, pushToolStart, pushToolEnd } =
      useAgentActivityStore.getState();
    startRun('t1', 'NOUS Agent', 'task');
    pushToolStart('t1', 'arxiv_search');
    pushToolEnd('t1', 'arxiv_search', true);
    expect(getRun('t1').steps[0].status).toBe('done');
  });

  it('pushToolEnd with ok=false flips to error', () => {
    const { startRun, pushToolStart, pushToolEnd } =
      useAgentActivityStore.getState();
    startRun('t1', 'NOUS Agent', 'task');
    pushToolStart('t1', 'arxiv_search');
    pushToolEnd('t1', 'arxiv_search', false);
    expect(getRun('t1').steps[0].status).toBe('error');
  });

  it('pushToolEnd for unknown tool is ignored', () => {
    const { startRun, pushToolEnd } = useAgentActivityStore.getState();
    startRun('t1', 'NOUS Agent', 'task');
    pushToolEnd('t1', 'nothing_here', true);
    expect(getRun('t1').steps).toEqual([]);
  });

  it('finishRun transitions running → done', () => {
    const { startRun, finishRun } = useAgentActivityStore.getState();
    startRun('t1', 'NOUS Agent', 'task');
    finishRun('t1', 'done');
    expect(getRun('t1').state).toBe('done');
  });

  it('finishRun transitions running → error', () => {
    const { startRun, finishRun } = useAgentActivityStore.getState();
    startRun('t1', 'NOUS Agent', 'task');
    finishRun('t1', 'error');
    expect(getRun('t1').state).toBe('error');
  });

  it('runs are isolated per thread', () => {
    const { startRun, pushToolStart } = useAgentActivityStore.getState();
    startRun('t1', 'A', 'taskA');
    startRun('t2', 'B', 'taskB');
    pushToolStart('t1', 'arxiv_search');
    expect(getRun('t1').steps).toHaveLength(1);
    expect(getRun('t2').steps).toHaveLength(0);
    expect(getRun('t1').name).toBe('A');
    expect(getRun('t2').name).toBe('B');
  });

  it('startRun on existing thread replaces prior run', () => {
    const { startRun, pushToolStart } = useAgentActivityStore.getState();
    startRun('t1', 'A', 'first');
    pushToolStart('t1', 'arxiv_search');
    startRun('t1', 'A', 'second');
    expect(getRun('t1').task).toBe('second');
    expect(getRun('t1').steps).toEqual([]);
  });
});

describe('agentActivityStore — currentThreadId lifecycle', () => {
  beforeEach(() => {
    useAgentActivityStore.setState({ runs: {}, currentThreadId: null });
  });

  it('startRun sets currentThreadId to the new thread', () => {
    useAgentActivityStore.getState().startRun('t1', 'A', 'task');
    expect(useAgentActivityStore.getState().currentThreadId).toBe('t1');
  });

  it('finishRun clears currentThreadId when the finishing thread is current', () => {
    const { startRun, finishRun } = useAgentActivityStore.getState();
    startRun('t1', 'A', 'task');
    finishRun('t1', 'done');
    expect(useAgentActivityStore.getState().currentThreadId).toBeNull();
  });

  it('finishRun does not change currentThreadId when finishing a different thread', () => {
    const { startRun, finishRun } = useAgentActivityStore.getState();
    startRun('t1', 'A', 'task');
    startRun('t2', 'B', 'task'); // t2 is now current
    finishRun('t1', 'done'); // t1 finishes, t2 still current
    expect(useAgentActivityStore.getState().currentThreadId).toBe('t2');
  });
});

describe('agentActivityStore — no-op updates do not notify subscribers', () => {
  beforeEach(() => {
    useAgentActivityStore.setState({ runs: {}, currentThreadId: null });
  });

  it('pushToolStart for unknown thread does not notify subscribers', () => {
    let calls = 0;
    const unsub = useAgentActivityStore.subscribe(() => {
      calls++;
    });
    useAgentActivityStore.getState().pushToolStart('t-missing', 'arxiv_search');
    unsub();
    expect(calls).toBe(0);
  });

  it('pushToolEnd for unknown thread does not notify subscribers', () => {
    let calls = 0;
    const unsub = useAgentActivityStore.subscribe(() => {
      calls++;
    });
    useAgentActivityStore
      .getState()
      .pushToolEnd('t-missing', 'arxiv_search', true);
    unsub();
    expect(calls).toBe(0);
  });

  it('finishRun for unknown thread does not notify subscribers', () => {
    let calls = 0;
    const unsub = useAgentActivityStore.subscribe(() => {
      calls++;
    });
    useAgentActivityStore.getState().finishRun('t-missing', 'done');
    unsub();
    expect(calls).toBe(0);
  });

  it('duplicate pushToolStart does not notify subscribers', () => {
    const { startRun, pushToolStart } = useAgentActivityStore.getState();
    startRun('t1', 'A', 'task');
    pushToolStart('t1', 'arxiv_search');
    let calls = 0;
    const unsub = useAgentActivityStore.subscribe(() => {
      calls++;
    });
    pushToolStart('t1', 'arxiv_search'); // de-duped, no-op
    unsub();
    expect(calls).toBe(0);
  });
});
