import {
  mapChatMessageToViewModel,
  mapSearchResultToChatMessages,
} from '../messageViewModel';

describe('messageViewModel', () => {
  it('maps chat route messages into shared view model', () => {
    const result = mapChatMessageToViewModel({
      id: 'm-1',
      role: 'assistant',
      content: 'Hello there',
      timestamp: 1700000000000,
      citations: [
        {
          documentId: 'doc-1',
          title: 'Doc 1',
          score: 0.93,
        },
      ],
    });

    expect(result.role).toBe('assistant');
    expect(result.content).toBe('Hello there');
    expect(result.citations?.[0].title).toBe('Doc 1');
  });

  it('maps search result into user and assistant messages', () => {
    const messages = mapSearchResultToChatMessages({
      query: 'What is RAG?',
      answer: {
        text: 'RAG combines retrieval and generation.',
        sources: [
          {
            document_id: 'doc-1',
            document_title: 'RAG Intro',
            snippet: 'RAG intro snippet',
            confidence: 0.81,
            file_type: 'pdf',
          },
        ],
      },
    } as any);

    expect(messages).toHaveLength(2);
    expect(messages[0].role).toBe('user');
    expect(messages[1].role).toBe('assistant');
    expect(messages[1].citations?.[0].title).toBe('RAG Intro');
  });

  it('normalizes malformed citation titles to stable source labels', () => {
    const messages = mapSearchResultToChatMessages({
      query: 'hello',
      answer: {
        text: 'hi',
        sources: [
          {
            document_id: 'doc-1',
            document_title: 'message body /verified 0/100...',
            snippet: 'message body /verified 0/100...',
            confidence: 0.09,
            file_type: 'pdf',
          },
          {
            document_id: 'doc-2',
            document_title: '   ',
            snippet: 'Fallback snippet content',
            confidence: 0.2,
            file_type: 'pdf',
          },
        ],
      },
    } as any);

    expect(messages[1].citations?.[0].title).toBe('Source 1');
    expect(messages[1].citations?.[1].title).toBe('Source 2');
  });
});
