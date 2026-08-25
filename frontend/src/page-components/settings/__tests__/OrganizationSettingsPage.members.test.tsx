import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import OrganizationSettingsPage from '../OrganizationSettingsPage';
import { useAuthStore } from '@/stores/authStore';
import type { User } from '@/types/auth';
import type { WorkspaceDetail, WorkspaceMember } from '@/types/workspace';

const workspaceApiMock = vi.hoisted(() => ({
  getOrCreateDefaultWorkspace: vi.fn(),
  getWorkspace: vi.fn(),
  addWorkspaceMember: vi.fn(),
  updateWorkspaceMember: vi.fn(),
  removeWorkspaceMember: vi.fn(),
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: workspaceApiMock,
}));

const owner: User = {
  id: 'owner-id',
  email: 'owner@example.com',
  name: 'Workspace Owner',
  organization_id: 'org-1',
  role: 'admin',
  storage_quota_used: 0,
  storage_quota_limit: 1024,
  created_at: '2026-01-01T00:00:00Z',
  last_login: '2026-08-25T00:00:00Z',
};

const member: WorkspaceMember = {
  id: 'membership-1',
  workspace_id: 'workspace-1',
  user_id: 'member-id',
  user_name: 'Ada Lovelace',
  user_email: 'ada@example.com',
  role: 'viewer',
  invited_by_id: owner.id,
  created_at: '2026-08-24T00:00:00Z',
  joined_at: '2026-08-24T00:00:00Z',
  updated_at: '2026-08-24T00:00:00Z',
};

const workspace: WorkspaceDetail = {
  id: 'workspace-1',
  name: 'Research workspace',
  description: null,
  organization_id: 'org-1',
  owner_id: owner.id,
  is_public: false,
  is_archived: false,
  member_count: 2,
  collection_count: 0,
  conversation_count: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-08-25T00:00:00Z',
  members: [
    {
      ...member,
      id: 'membership-owner',
      user_id: owner.id,
      user_name: owner.name,
      user_email: owner.email,
      role: 'owner',
    },
    member,
  ],
};

describe('OrganizationSettingsPage member management', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: owner });
    workspaceApiMock.getOrCreateDefaultWorkspace.mockReset();
    workspaceApiMock.getWorkspace.mockReset();
    workspaceApiMock.addWorkspaceMember.mockReset();
    workspaceApiMock.updateWorkspaceMember.mockReset();
    workspaceApiMock.removeWorkspaceMember.mockReset();
    workspaceApiMock.getOrCreateDefaultWorkspace.mockResolvedValue({
      id: workspace.id,
    });
    workspaceApiMock.getWorkspace.mockResolvedValue(workspace);
  });

  it('loads members and wires add, role update, and remove actions', async () => {
    const user = userEvent.setup();
    const addedMember = {
      ...member,
      user_id: 'new-member-id',
      user_name: 'Grace Hopper',
      user_email: 'grace@example.com',
    };
    const updatedMember = { ...member, role: 'editor' as const };
    workspaceApiMock.addWorkspaceMember.mockResolvedValue(addedMember);
    workspaceApiMock.updateWorkspaceMember.mockResolvedValue(updatedMember);
    workspaceApiMock.removeWorkspaceMember.mockResolvedValue(undefined);
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<OrganizationSettingsPage />);

    expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument();

    await user.type(
      screen.getByLabelText('Add member by user ID'),
      'new-member-id'
    );
    await user.click(screen.getByRole('button', { name: 'Add member' }));
    expect(workspaceApiMock.addWorkspaceMember).toHaveBeenCalledWith(
      workspace.id,
      { user_id: 'new-member-id', role: 'viewer' }
    );

    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Role for Ada Lovelace' }),
      'editor'
    );
    await waitFor(() =>
      expect(workspaceApiMock.updateWorkspaceMember).toHaveBeenCalledWith(
        workspace.id,
        member.user_id,
        { role: 'editor' }
      )
    );

    await user.click(screen.getByRole('button', { name: 'Remove Ada Lovelace' }));
    await waitFor(() =>
      expect(workspaceApiMock.removeWorkspaceMember).toHaveBeenCalledWith(
        workspace.id,
        member.user_id
      )
    );
  });
});
