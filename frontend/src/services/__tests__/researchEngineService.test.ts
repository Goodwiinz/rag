import {
  listProjects,
  createProject,
  getProject,
  listTemplates,
  createBlueprint,
  getBlueprint,
  startRun,
  getRun,
  pauseRun,
  resumeRun,
  getRunManifest,
  listSteps,
  getStep,
} from '../researchEngineService';
import { apiClient } from '../apiClient';

jest.mock('../apiClient', () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

const mockApiClient = apiClient as jest.Mocked<typeof apiClient>;

const BASE = '/api/v1/research-engine';

describe('researchEngineService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('listProjects', () => {
    it('calls GET /projects', async () => {
      mockApiClient.get.mockResolvedValue([]);
      await listProjects();
      expect(mockApiClient.get).toHaveBeenCalledWith(`${BASE}/projects`);
    });
  });

  describe('createProject', () => {
    it('calls POST /projects with data', async () => {
      const data = { name: 'Test Project', description: 'A test' };
      mockApiClient.post.mockResolvedValue({ id: '1', ...data });
      await createProject(data);
      expect(mockApiClient.post).toHaveBeenCalledWith(`${BASE}/projects`, data);
    });
  });

  describe('getProject', () => {
    it('calls GET /projects/:id', async () => {
      mockApiClient.get.mockResolvedValue({ id: 'p1' });
      await getProject('p1');
      expect(mockApiClient.get).toHaveBeenCalledWith(`${BASE}/projects/p1`);
    });
  });

  describe('listTemplates', () => {
    it('calls GET /blueprints/templates', async () => {
      mockApiClient.get.mockResolvedValue([]);
      await listTemplates();
      expect(mockApiClient.get).toHaveBeenCalledWith(
        `${BASE}/blueprints/templates`
      );
    });
  });

  describe('createBlueprint', () => {
    it('calls POST /blueprints/projects/:projectId with data', async () => {
      const data = {
        name: 'Blueprint 1',
        steps: [
          {
            type: 'search',
            name: 'step1',
            parameters: {},
            mode: 'deterministic' as const,
          },
        ],
        parameters: { key: 'value' },
      };
      mockApiClient.post.mockResolvedValue({ id: 'b1' });
      await createBlueprint('p1', data);
      expect(mockApiClient.post).toHaveBeenCalledWith(
        `${BASE}/blueprints/projects/p1`,
        data
      );
    });
  });

  describe('getBlueprint', () => {
    it('calls GET /blueprints/:id', async () => {
      mockApiClient.get.mockResolvedValue({ id: 'b1' });
      await getBlueprint('b1');
      expect(mockApiClient.get).toHaveBeenCalledWith(`${BASE}/blueprints/b1`);
    });
  });

  describe('startRun', () => {
    it('calls POST /blueprints/:blueprintId/runs with parameters_override', async () => {
      const params = { temperature: 0.5 };
      mockApiClient.post.mockResolvedValue({ id: 'r1' });
      await startRun('b1', params);
      expect(mockApiClient.post).toHaveBeenCalledWith(
        `${BASE}/blueprints/b1/runs`,
        { parameters_override: params }
      );
    });
  });

  describe('getRun', () => {
    it('calls GET /runs/:runId', async () => {
      mockApiClient.get.mockResolvedValue({ id: 'r1' });
      await getRun('r1');
      expect(mockApiClient.get).toHaveBeenCalledWith(`${BASE}/runs/r1`);
    });
  });

  describe('pauseRun', () => {
    it('calls POST /runs/:runId/pause', async () => {
      mockApiClient.post.mockResolvedValue({ status: 'paused' });
      await pauseRun('r1');
      expect(mockApiClient.post).toHaveBeenCalledWith(`${BASE}/runs/r1/pause`);
    });
  });

  describe('resumeRun', () => {
    it('calls POST /runs/:runId/resume', async () => {
      mockApiClient.post.mockResolvedValue({ status: 'running' });
      await resumeRun('r1');
      expect(mockApiClient.post).toHaveBeenCalledWith(`${BASE}/runs/r1/resume`);
    });
  });

  describe('getRunManifest', () => {
    it('calls GET /runs/:runId/manifest', async () => {
      mockApiClient.get.mockResolvedValue({ manifest: {} });
      await getRunManifest('r1');
      expect(mockApiClient.get).toHaveBeenCalledWith(
        `${BASE}/runs/r1/manifest`
      );
    });
  });

  describe('listSteps', () => {
    it('calls GET /runs/:runId/steps', async () => {
      mockApiClient.get.mockResolvedValue([]);
      await listSteps('r1');
      expect(mockApiClient.get).toHaveBeenCalledWith(`${BASE}/runs/r1/steps`);
    });
  });

  describe('getStep', () => {
    it('calls GET /steps/:stepId', async () => {
      mockApiClient.get.mockResolvedValue({ id: 's1' });
      await getStep('s1');
      expect(mockApiClient.get).toHaveBeenCalledWith(`${BASE}/steps/s1`);
    });
  });
});
