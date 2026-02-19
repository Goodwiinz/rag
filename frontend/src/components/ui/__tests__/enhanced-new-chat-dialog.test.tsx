import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { EnhancedNewChatDialog } from '../enhanced-new-chat-dialog';
import { Assistant } from '@/types/chat';

// Mock dependencies
// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

const mockAssistants: Assistant[] = [
  {
    id: 'asst_1',
    name: 'Research Assistant',
    description: 'Helps with research tasks',
    category: 'academic',
    capabilities: ['Research', 'Analysis'],
    color: 'from-blue-500 to-cyan-500',
    isActive: true,
  },
  {
    id: 'asst_2',
    name: 'Coding Helper',
    description: 'Writes code for you',
    category: 'development',
    capabilities: ['Python', 'TypeScript'],
    color: 'from-green-500 to-emerald-500',
  },
];

describe('EnhancedNewChatDialog Accessibility', () => {
  it('renders assistant cards as buttons', () => {
    const handleSelect = jest.fn();
    const handleOpenChange = jest.fn();

    render(
      <EnhancedNewChatDialog
        open={true}
        onOpenChange={handleOpenChange}
        assistants={mockAssistants}
        onSelectAssistant={handleSelect}
      />
    );

    // This should find the button with the assistant name
    // Currently, it will fail because it's a div
    const assistantButton = screen.getByRole('button', { name: /Research Assistant/i });
    expect(assistantButton).toBeInTheDocument();

    // Verify it's clickable via keyboard
    assistantButton.focus();
    expect(assistantButton).toHaveFocus();

    fireEvent.click(assistantButton);

    // Clicking calls onSelectAssistant internally, but the dialog manages state.
    // To verify onSelectAssistant is called, we need to click "Start Conversation".

    // Find "Start Conversation" button
    const startButton = screen.getByRole('button', { name: /Start Conversation/i });
    expect(startButton).toBeEnabled();

    fireEvent.click(startButton);

    // onSelectAssistant should be called with the selected assistant
    expect(handleSelect).toHaveBeenCalledWith(expect.objectContaining({
        name: 'Research Assistant'
    }));
  });
});
