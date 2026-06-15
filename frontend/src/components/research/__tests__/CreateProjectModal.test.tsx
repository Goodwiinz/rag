import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { CreateProjectModal } from '@/components/research/CreateProjectModal';

describe('CreateProjectModal', () => {
  it('does not render when closed', () => {
    const { container } = render(
      <CreateProjectModal
        isOpen={false}
        onClose={vi.fn()}
        onCreate={vi.fn().mockResolvedValue(undefined)}
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it('submits form payload including tags and type', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <CreateProjectModal
        isOpen
        onClose={onClose}
        onCreate={onCreate}
      />
    );

    fireEvent.change(screen.getByPlaceholderText('e.g. ML Healthcare review'), {
      target: { value: 'ML Healthcare' },
    });
    fireEvent.change(screen.getByPlaceholderText('Short project summary'), {
      target: { value: 'Project description' },
    });

    // shadcn Select — click the trigger to open, then select an option
    fireEvent.click(screen.getByRole('combobox', { name: /type/i }));
    await waitFor(() => {
      fireEvent.click(screen.getByRole('option', { name: /thesis/i }));
    });

    fireEvent.change(screen.getByPlaceholderText('Add a tag'), {
      target: { value: 'ml' },
    });
    fireEvent.click(screen.getByRole('button', { name: /add tag/i }));

    fireEvent.click(screen.getByRole('button', { name: /create project/i }));

    await waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'ML Healthcare',
          description: 'Project description',
          project_type: 'thesis',
          tags: ['ml'],
        })
      );
      expect(onClose).toHaveBeenCalled();
    });
  });
});
