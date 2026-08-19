/**
 * Round-3 L17: Escape inside the approval card must not also reach the chat
 * panel's own Escape handler and close the whole surface.
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ConfirmationCard } from '../ConfirmationCard';

describe('ConfirmationCard escape handling', () => {
  it('cancels the confirmation without bubbling the keypress', () => {
    const onCancel = vi.fn();
    const panelKeyDown = vi.fn();

    render(
      <div onKeyDown={panelKeyDown}>
        <ConfirmationCard
          tools={[{ name: 'ingest_arxiv_papers', args: {} }]}
          message="The agent wants to perform an action."
          onConfirm={vi.fn()}
          onCancel={onCancel}
          isLoading={false}
        />
      </div>
    );

    fireEvent.keyDown(screen.getByRole('alertdialog'), { key: 'Escape' });

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(panelKeyDown).not.toHaveBeenCalled();
  });
});
