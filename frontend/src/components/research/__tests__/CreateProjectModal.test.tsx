import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { CreateProjectModal } from '@/components/research/CreateProjectModal';

describe('CreateProjectModal', () => {
  it('does not render when closed', () => {
    const { container } = render(
      <CreateProjectModal
        isOpen={false}
        onClose={jest.fn()}
        onCreate={jest.fn().mockResolvedValue(undefined)}
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it('submits form payload including tags and type', async () => {
    const onCreate = jest.fn().mockResolvedValue(undefined);
    const onClose = jest.fn();

    render(
      <CreateProjectModal
        isOpen
        onClose={onClose}
        onCreate={onCreate}
      />
    );

    fireEvent.change(screen.getByPlaceholderText('e.g., ML Healthcare'), {
      target: { value: 'ML Healthcare' },
    });
    fireEvent.change(screen.getByPlaceholderText('Short project summary'), {
      target: { value: 'Project description' },
    });
    fireEvent.change(screen.getByDisplayValue('Research'), {
      target: { value: 'thesis' },
    });

    fireEvent.change(screen.getByPlaceholderText('Add tag and press Enter'), {
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
