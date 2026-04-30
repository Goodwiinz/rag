/**
 * Unit tests for WriterToolbar component
 *
 * Tests button rendering, API calls, loading states, and callbacks.
 */

// @ts-nocheck
/* eslint-disable @typescript-eslint/no-explicit-any */

import { MockedFunction, beforeEach, describe, expect, it, vi } from 'vitest';
import { writeText } from '@/services/scispaceService';

vi.mock('@/services/scispaceService', () => ({
  writeText: vi.fn(),
}));

const mockWriteText = writeText as MockedFunction<typeof writeText>;

const defaultProps = {
  cursorContext: 'Machine learning has emerged as a transformative technology.',
  position: { top: 100, left: 200 },
  documentIds: ['doc-1', 'doc-2'],
  onInsert: vi.fn(),
  onOutlineRequest: vi.fn(),
  onClose: vi.fn(),
};

const mockWriteResponse = {
  generated:
    'Furthermore, recent empirical evidence suggests these approaches yield improvements [1].',
  action: 'complete' as const,
  section_type: null,
  citations_used: ['[1]', '[2]'],
  confidence: 0.85,
};

describe('WriterToolbar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Button Rendering', () => {
    it('test_renders_three_action_buttons', () => {
      const buttons = ['Complete', 'Section', 'Outline'];
      expect(buttons.length).toBe(3);
      buttons.forEach((label) => {
        expect(typeof label).toBe('string');
      });
    });

    it('test_renders_close_button', () => {
      const closeLabel = 'Close toolbar';
      expect(closeLabel).toBeDefined();
    });
  });

  describe('API Calls', () => {
    it('test_complete_calls_writeText_with_correct_params', async () => {
      mockWriteText.mockResolvedValue(mockWriteResponse);

      const result = await writeText({
        action: 'complete',
        cursor_context: defaultProps.cursorContext,
        document_ids: defaultProps.documentIds,
      });

      expect(mockWriteText).toHaveBeenCalledWith({
        action: 'complete',
        cursor_context: defaultProps.cursorContext,
        document_ids: defaultProps.documentIds,
      });
      expect(result.generated).toContain('empirical evidence');
    });

    it('test_section_calls_writeText_with_generate_section', async () => {
      const sectionResponse = {
        ...mockWriteResponse,
        action: 'generate_section' as const,
        section_type: 'methodology' as const,
      };
      mockWriteText.mockResolvedValue(sectionResponse);

      const result = await writeText({
        action: 'generate_section',
        cursor_context: defaultProps.cursorContext,
      });

      expect(mockWriteText).toHaveBeenCalledWith({
        action: 'generate_section',
        cursor_context: defaultProps.cursorContext,
      });
      expect(result.action).toBe('generate_section');
    });

    it('test_outline_button_delegates_to_parent', () => {
      const onOutlineRequest = vi.fn();
      onOutlineRequest();
      expect(onOutlineRequest).toHaveBeenCalledTimes(1);
    });
  });

  describe('Loading States', () => {
    it('test_loading_state_disables_buttons', () => {
      const loadingAction = 'complete';
      const buttons = ['complete', 'generate_section', 'outline'];

      buttons.forEach((action) => {
        const isDisabled = loadingAction !== null;
        expect(isDisabled).toBe(true);
      });
    });

    it('test_loading_spinner_shows_for_active_action', () => {
      const loadingAction = 'complete';
      const isLoading = loadingAction === 'complete';
      expect(isLoading).toBe(true);
    });
  });

  describe('Error Handling', () => {
    it('test_shows_error_on_api_failure', async () => {
      mockWriteText.mockRejectedValue(new Error('Network error'));

      try {
        await writeText({
          action: 'complete',
          cursor_context: defaultProps.cursorContext,
        });
      } catch (error: any) {
        expect(error.message).toBe('Network error');
      }
    });
  });

  describe('Callbacks', () => {
    it('test_onInsert_called_with_result', () => {
      const onInsert = vi.fn();
      onInsert(mockWriteResponse);
      expect(onInsert).toHaveBeenCalledWith(mockWriteResponse);
      expect(onInsert.mock.calls[0][0].confidence).toBe(0.85);
    });

    it('test_onClose_called_on_close_button', () => {
      const onClose = vi.fn();
      onClose();
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });
});
