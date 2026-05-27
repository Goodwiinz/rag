import { describe, expect, it } from 'vitest';
import { buildThreadCreateRequest } from '../threadCreation';

describe('buildThreadCreateRequest', () => {
  it('does not embed the first user message in thread creation', () => {
    expect(
      buildThreadCreateRequest({
        conversationId: 'conv-123',
        title: 'What is machine learning',
      })
    ).toEqual({
      conversation_id: 'conv-123',
      title: 'What is machine learning',
    });
  });

  it('includes project_id when chat is bound to a project', () => {
    expect(
      buildThreadCreateRequest({
        conversationId: 'conv-123',
        title: 'Project discussion',
        projectId: 'project-456',
      })
    ).toEqual({
      conversation_id: 'conv-123',
      title: 'Project discussion',
      project_id: 'project-456',
    });
  });
});
