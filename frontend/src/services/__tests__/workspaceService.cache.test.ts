describe('workspaceService default workspace cache', () => {
  beforeEach(() => {
    jest.resetModules();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('revalidates a cached workspace before returning it', async () => {
    let workspaceService: typeof import('@/services/workspaceService').workspaceService;

    jest.isolateModules(() => {
      ({ workspaceService } = require('@/services/workspaceService'));
    });

    const cachedWorkspace = {
      id: 'ws-1',
      name: 'Cached Workspace',
      created_at: '2026-04-01T00:00:00Z',
      updated_at: '2026-04-01T00:00:00Z',
    };
    const freshWorkspace = {
      ...cachedWorkspace,
      name: 'Fresh Workspace',
      collection_count: 4,
      conversation_count: 9,
    };

    localStorage.setItem(
      'default-workspace-object',
      JSON.stringify(cachedWorkspace)
    );
    localStorage.setItem(
      'default-workspace-cached-at',
      String(Date.now())
    );

    const getWorkspaceSpy = jest
      .spyOn(workspaceService, 'getWorkspace')
      .mockResolvedValue(freshWorkspace as any);
    const listWorkspacesSpy = jest
      .spyOn(workspaceService, 'listWorkspaces')
      .mockResolvedValue([]);

    const result = await workspaceService.getOrCreateDefaultWorkspace();

    expect(getWorkspaceSpy).toHaveBeenCalledWith('ws-1');
    expect(listWorkspacesSpy).not.toHaveBeenCalled();
    expect(result).toEqual(freshWorkspace);
  });

  it('drops a deleted cached workspace and falls back to the server list', async () => {
    let workspaceService: typeof import('@/services/workspaceService').workspaceService;

    jest.isolateModules(() => {
      ({ workspaceService } = require('@/services/workspaceService'));
    });

    localStorage.setItem(
      'default-workspace-object',
      JSON.stringify({
        id: 'deleted-ws',
        name: 'Deleted Workspace',
        created_at: '2026-04-01T00:00:00Z',
        updated_at: '2026-04-01T00:00:00Z',
      })
    );
    localStorage.setItem(
      'default-workspace-cached-at',
      String(Date.now())
    );

    jest.spyOn(workspaceService, 'getWorkspace').mockRejectedValue({
      response: { status: 404 },
    });

    const liveWorkspace = {
      id: 'live-ws',
      name: 'Live Workspace',
      collection_count: 2,
      conversation_count: 3,
      created_at: '2026-04-02T00:00:00Z',
      updated_at: '2026-04-02T00:00:00Z',
    };

    const listWorkspacesSpy = jest
      .spyOn(workspaceService, 'listWorkspaces')
      .mockResolvedValue([liveWorkspace as any]);

    const result = await workspaceService.getOrCreateDefaultWorkspace();

    expect(listWorkspacesSpy).toHaveBeenCalledTimes(1);
    expect(result).toEqual(liveWorkspace);
    expect(localStorage.getItem('default-workspace-object')).toContain(
      'live-ws'
    );
  });
});
