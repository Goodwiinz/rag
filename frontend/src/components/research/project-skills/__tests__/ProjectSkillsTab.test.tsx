import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fireEvent, render, screen, waitFor } from '@/test/test-utils';
import { ProjectSkillsTab } from '@/components/research/ProjectSkillsTab';
import { projectSkillService } from '@/services/projectSkillService';

vi.mock('@/services/projectSkillService', () => ({
  projectSkillService: {
    list: vi.fn(), get: vi.fn(), getDiff: vi.fn(), approve: vi.fn(),
    create: vi.fn(), proposeVersion: vi.fn(), reject: vi.fn(), rescan: vi.fn(),
    archive: vi.fn(), restore: vi.fn(), rollback: vi.fn(),
  },
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ user: { id: 'user-1' } }),
}));

const skill = {
  id: 'skill-1', name: 'release-notes', active_version_id: 'version-1', is_archived: false,
  active_version: { id: 'version-1', name: 'release-notes', version: 1, description: 'Writes release notes', document_text: '# v1', content_hash: 'hash', scan_state: 'clean', scan_findings: [] },
};
const pending = {
  id: 'request-1', skill_id: 'skill-1', skill_name: 'release-notes', action: 'activate',
  requester_id: 'user-2', reviewer_id: null, reviewed_at: null, created_at: '2026-07-19T00:00:00Z',
  expected_active_version_id: 'version-1', proposed_version_id: 'version-2', status: 'pending', audit_note: null, warning_acknowledged: false,
};

function renderCatalog(overrides: Record<string, unknown> = {}) {
  vi.mocked(projectSkillService.list).mockResolvedValue({
    skills: [skill], pending_change_requests: [pending], capabilities: { can_edit: true, can_admin: true }, ...overrides,
  } as never);
  vi.mocked(projectSkillService.getDiff).mockResolvedValue({ from_version: 1, to_version: 2, diff: '' } as never);
  return render(<ProjectSkillsTab projectId="project-1" />);
}

describe('ProjectSkillsTab', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows active skill metadata, pending status, and an accessible empty state when no skills exist', async () => {
    renderCatalog();
    expect(await screen.findByText('release-notes')).toBeInTheDocument();
    expect(screen.getByText('Writes release notes')).toBeInTheDocument();
    expect(screen.getByText('Active v1')).toBeInTheDocument();
    expect(screen.getByText('Pending approval')).toBeInTheDocument();

    vi.mocked(projectSkillService.list).mockResolvedValueOnce({ skills: [], pending_change_requests: [], capabilities: { can_edit: true, can_admin: false } } as never);
    const { unmount } = render(<ProjectSkillsTab projectId="project-empty" />);
    expect(await screen.findByRole('status')).toHaveTextContent('No project skills yet');
    unmount();
  });

  it('lets an editor propose a document without exposing approval controls', async () => {
    renderCatalog({ capabilities: { can_edit: true, can_admin: false } });
    await screen.findByText('release-notes');
    fireEvent.click(screen.getByRole('button', { name: /new skill/i }));
    fireEvent.change(screen.getByLabelText('Skill document'), { target: { value: '---\nname: summaries\ndescription: Summarize source material\n---\nUse citations.' } });
    fireEvent.click(screen.getByRole('button', { name: /propose skill/i }));
    await waitFor(() => expect(projectSkillService.create).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: /^approve$/i })).not.toBeInTheDocument();
  });

  it('blocks approval for blocker findings and requires warning acknowledgement and a note', async () => {
    vi.mocked(projectSkillService.get).mockResolvedValue({ ...skill, versions: [{ ...skill.active_version, id: 'version-2', version: 2, scan_findings: [{ code: 'secret', severity: 'blocker', message: 'Secret found', line: 4 }] }] } as never);
    renderCatalog();
    await screen.findByText('release-notes');
    fireEvent.click(screen.getByRole('button', { name: /review release-notes/i }));
    await waitFor(() => expect(projectSkillService.get).toHaveBeenCalledWith('project-1', 'release-notes'));
    expect(await screen.findByText('Review pending change')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^approve$/i })).toBeDisabled();
  });

  it('stages rollback from immutable history and explains a stale approval conflict', async () => {
    vi.mocked(projectSkillService.get).mockResolvedValue({ ...skill, versions: [{ ...skill.active_version, version: 2, id: 'version-2' }, skill.active_version] } as never);
    vi.mocked(projectSkillService.rollback).mockResolvedValue(pending as never);
    vi.mocked(projectSkillService.approve).mockRejectedValue({ error: { status_code: 409 } });
    renderCatalog();
    await screen.findByText('release-notes');
    fireEvent.click(screen.getByRole('button', { name: /review release-notes/i }));
    expect(await screen.findByText('Version history')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /stage rollback to v2/i }));
    await waitFor(() => expect(projectSkillService.rollback).toHaveBeenCalledWith('project-1', 'release-notes', { version_id: 'version-2' }));
    fireEvent.click(screen.getByRole('button', { name: /^approve$/i }));
    expect(await screen.findByText(/superseded by a newer change/i)).toBeInTheDocument();
  });
});
