import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProjectList } from '@/components/research/ProjectList';
import type { Project } from '@/services/projectService';

const mockProjects: Project[] = [
  {
    id: 'p1',
    workspace_id: 'w1',
    name: 'ML Healthcare',
    description: 'Research on ML in healthcare',
    research_status: 'active',
    project_type: 'research',
    tags: ['ml', 'healthcare'],
    document_count: 3,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'p2',
    workspace_id: 'w1',
    name: 'NLP Survey',
    description: 'Survey papers',
    research_status: 'paused',
    project_type: 'literature_review',
    tags: ['nlp'],
    document_count: 1,
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
];

describe('ProjectList', () => {
  it('renders projects and opens selected project', () => {
    const onOpenProject = jest.fn();

    render(
      <ProjectList
        projects={mockProjects}
        viewMode="grid"
        onViewModeChange={jest.fn()}
        onOpenProject={onOpenProject}
      />
    );

    expect(screen.getByText('ML Healthcare')).toBeInTheDocument();
    expect(screen.getByText('NLP Survey')).toBeInTheDocument();

    fireEvent.click(screen.getByText('ML Healthcare'));
    expect(onOpenProject).toHaveBeenCalledWith('p1');
  });

  it('changes view mode when toggle is clicked', () => {
    const onViewModeChange = jest.fn();

    render(
      <ProjectList
        projects={mockProjects}
        viewMode="grid"
        onViewModeChange={onViewModeChange}
        onOpenProject={jest.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /list/i }));
    expect(onViewModeChange).toHaveBeenCalledWith('list');
  });

  it('triggers archive and delete actions', async () => {
    const user = userEvent.setup();
    const onArchiveProject = jest.fn();
    const onDeleteProject = jest.fn();

    render(
      <ProjectList
        projects={mockProjects}
        viewMode="grid"
        onViewModeChange={jest.fn()}
        onOpenProject={jest.fn()}
        onArchiveProject={onArchiveProject}
        onDeleteProject={onDeleteProject}
      />
    );

    // Open the dropdown for the first project card and click Archive
    await user.click(
      screen.getAllByRole('button', { name: /project actions/i })[0]
    );
    await user.click(screen.getByText('Archive'));
    expect(onArchiveProject).toHaveBeenCalledWith('p1');

    // Open the dropdown again and click Delete
    await user.click(
      screen.getAllByRole('button', { name: /project actions/i })[0]
    );
    await user.click(screen.getByText('Delete'));
    expect(onDeleteProject).toHaveBeenCalledWith('p1');
  });
});
