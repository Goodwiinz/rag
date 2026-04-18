import {
  mapChatMessageToViewModel,
  mapSearchResultToChatMessages,
  type SearchResultChatMessageInput,
} from '../messageViewModel';

function createSearchResultFixture(
  overrides: Partial<SearchResultChatMessageInput> = {}
): SearchResultChatMessageInput {
  const defaultFixture: SearchResultChatMessageInput = {
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
  };

  return {
    query: overrides.query ?? defaultFixture.query,
    answer: {
      ...defaultFixture.answer,
      ...overrides.answer,
      sources: overrides.answer?.sources ?? defaultFixture.answer.sources,
    },
  };
}

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
    const messages = mapSearchResultToChatMessages(createSearchResultFixture());

    expect(messages).toHaveLength(2);
    expect(messages[0].role).toBe('user');
    expect(messages[1].role).toBe('assistant');
    expect(messages[1].citations?.[0].title).toBe('RAG Intro');
  });

  it('uses one timestamp for both mapped messages', () => {
    const nowSpy = jest
      .spyOn(Date, 'now')
      .mockReturnValueOnce(1700000000000)
      .mockReturnValueOnce(1700000000001);

    try {
      const messages = mapSearchResultToChatMessages(
        createSearchResultFixture()
      );

      expect(messages[0].timestamp).toBe(1700000000000);
      expect(messages[1].timestamp).toBe(1700000000000);
    } finally {
      nowSpy.mockRestore();
    }
  });

  it('normalizes malformed citation titles to stable source labels', () => {
    const messages = mapSearchResultToChatMessages(
      createSearchResultFixture({
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
      })
    );

    expect(messages[1].citations?.[0].title).toBe('Source 1');
    expect(messages[1].citations?.[1].title).toBe('Source 2');
  });

  it('maps deterministic metadata into assistant messages when present', () => {
    const messages = mapSearchResultToChatMessages(
      createSearchResultFixture({
        query: 'Summarize this trial',
        answer: {
          text: 'Trial showed improved outcomes.',
          sources: [],
          claims: ['Outcome improved by 20%'],
          confidence: 0.91,
          coverage: 0.84,
          decisionTraceId: 'trace_123',
        },
      })
    );

    expect(messages[1].role).toBe('assistant');
    expect(messages[1].claims).toEqual(['Outcome improved by 20%']);
    expect(messages[1].confidence).toBe(0.91);
    expect(messages[1].coverage).toBe(0.84);
    expect(messages[1].decisionTraceId).toBe('trace_123');
  });

  it('maps decision trace id from snake_case input to camelCase output', () => {
    const messages = mapSearchResultToChatMessages(
      createSearchResultFixture({
        answer: {
          text: 'Trial showed improved outcomes.',
          sources: [],
          decision_trace_id: 'trace_456',
        },
      })
    );

    expect(messages[1].decisionTraceId).toBe('trace_456');
  });
});
