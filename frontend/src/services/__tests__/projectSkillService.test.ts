import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from '@/services/api-client';
import { projectSkillService } from '@/services/projectSkillService';

vi.mock('@/services/api-client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

describe('projectSkillService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('uses the project skill endpoints and preserves generated request bodies', async () => {
    const catalog = { skills: [], pending_change_requests: [], capabilities: { can_edit: true, can_admin: false } };
    vi.mocked(api.get).mockResolvedValue(catalog);
    vi.mocked(api.post).mockResolvedValue({ id: 'request-1' });

    await expect(projectSkillService.list('project-1')).resolves.toBe(catalog);
    await projectSkillService.get('project-1', 'release-notes');
    await projectSkillService.getDiff('project-1', 'release-notes', 1, 2);
    await projectSkillService.create('project-1', { document_text: '# Release notes' });
    await projectSkillService.proposeVersion('project-1', 'release-notes', { document_text: '# v2' });
    await projectSkillService.approve('project-1', 'request-1', {
      self_approval_acknowledged: false,
      warning_acknowledged: true,
      audit_note: 'Reviewed scanner warning',
    });
    await projectSkillService.reject('project-1', 'request-1', { audit_note: 'Needs revision' });
    await projectSkillService.rescan('project-1', 'request-1');
    await projectSkillService.archive('project-1', 'release-notes');
    await projectSkillService.restore('project-1', 'release-notes');
    await projectSkillService.rollback('project-1', 'release-notes', { version_id: 'version-1' });

    expect(api.get).toHaveBeenNthCalledWith(1, '/projects/project-1/skills');
    expect(api.get).toHaveBeenNthCalledWith(2, '/projects/project-1/skills/release-notes');
    expect(api.get).toHaveBeenNthCalledWith(3, '/projects/project-1/skills/release-notes/diff?from_version=1&to_version=2');
    expect(api.post).toHaveBeenCalledWith('/projects/project-1/skills', { document_text: '# Release notes' });
    expect(api.post).toHaveBeenCalledWith('/projects/project-1/skills/release-notes/versions', { document_text: '# v2' });
    expect(api.post).toHaveBeenCalledWith('/projects/project-1/skills/change-requests/request-1/approve', expect.objectContaining({ warning_acknowledged: true }));
    expect(api.post).toHaveBeenCalledWith('/projects/project-1/skills/change-requests/request-1/reject', { audit_note: 'Needs revision' });
    expect(api.post).toHaveBeenCalledWith('/projects/project-1/skills/change-requests/request-1/rescan');
    expect(api.post).toHaveBeenCalledWith('/projects/project-1/skills/release-notes/archive');
    expect(api.post).toHaveBeenCalledWith('/projects/project-1/skills/release-notes/restore');
    expect(api.post).toHaveBeenCalledWith('/projects/project-1/skills/release-notes/rollback', { version_id: 'version-1' });
  });
});
