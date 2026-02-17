/**
 * Unit tests for Streaming Service
 *
 * Tests SSE line parsing logic. streamChatMessage is tested via integration tests.
 */

import { parseSSELine } from '../streamingService';
import type { StreamEvent, StreamEventType } from '../streamingService';

// ============================================================================
// parseSSELine
// ============================================================================

describe('parseSSELine', () => {
  // ==========================================================================
  // Valid event types
  // ==========================================================================

  describe('valid event types', () => {
    const validEventTypes: StreamEventType[] = [
      'message_start',
      'rag_context',
      'token',
      'citation_inline',
      'message_done',
      'error',
    ];

    it.each(validEventTypes)(
      'should parse a "%s" event with valid JSON data',
      (eventType) => {
        const data = { key: 'value', count: 42 };
        const result = parseSSELine(eventType, JSON.stringify(data));

        expect(result).toEqual({
          type: eventType,
          data: { key: 'value', count: 42 },
        });
      }
    );
  });

  // ==========================================================================
  // Data parsing
  // ==========================================================================

  describe('data parsing', () => {
    it('should parse a message_start event with message metadata', () => {
      const data = { message_id: 'msg-123', thread_id: 'thread-456' };
      const result = parseSSELine('message_start', JSON.stringify(data));

      expect(result).toEqual({
        type: 'message_start',
        data: { message_id: 'msg-123', thread_id: 'thread-456' },
      });
    });

    it('should parse a token event with content string', () => {
      const data = { content: 'Hello ' };
      const result = parseSSELine('token', JSON.stringify(data));

      expect(result).toEqual({
        type: 'token',
        data: { content: 'Hello ' },
      });
    });

    it('should parse a rag_context event with source documents', () => {
      const data = {
        sources: [
          { doc_id: 'doc-1', score: 0.95 },
          { doc_id: 'doc-2', score: 0.87 },
        ],
      };
      const result = parseSSELine('rag_context', JSON.stringify(data));

      expect(result).toEqual({
        type: 'rag_context',
        data,
      });
    });

    it('should parse a citation_inline event', () => {
      const data = {
        citation_id: 'cite-1',
        doc_id: 'doc-1',
        text: 'quoted text',
      };
      const result = parseSSELine('citation_inline', JSON.stringify(data));

      expect(result).toEqual({
        type: 'citation_inline',
        data,
      });
    });

    it('should parse a message_done event with completion metadata', () => {
      const data = { message_id: 'msg-123', token_count: 256 };
      const result = parseSSELine('message_done', JSON.stringify(data));

      expect(result).toEqual({
        type: 'message_done',
        data,
      });
    });

    it('should parse an error event', () => {
      const data = { code: 'rate_limit', message: 'Too many requests' };
      const result = parseSSELine('error', JSON.stringify(data));

      expect(result).toEqual({
        type: 'error',
        data,
      });
    });

    it('should parse empty JSON object', () => {
      const result = parseSSELine('message_start', '{}');

      expect(result).toEqual({
        type: 'message_start',
        data: {},
      });
    });

    it('should parse nested JSON objects', () => {
      const data = {
        metadata: {
          model: 'gpt-4',
          settings: { temperature: 0.7 },
        },
      };
      const result = parseSSELine('message_start', JSON.stringify(data));

      expect(result).toEqual({
        type: 'message_start',
        data,
      });
    });
  });

  // ==========================================================================
  // Invalid input handling
  // ==========================================================================

  describe('invalid input handling', () => {
    it('should return null for invalid JSON data', () => {
      const result = parseSSELine('token', 'not valid json');

      expect(result).toBeNull();
    });

    it('should return null for incomplete JSON data', () => {
      const result = parseSSELine('token', '{"key": "value"');

      expect(result).toBeNull();
    });

    it('should return null for empty string data', () => {
      const result = parseSSELine('token', '');

      expect(result).toBeNull();
    });

    it('should return null when data is a JSON string (not object)', () => {
      const result = parseSSELine('token', '"just a string"');

      expect(result).toBeNull();
    });

    it('should return null when data is a JSON array', () => {
      const result = parseSSELine('token', '[1, 2, 3]');

      expect(result).toBeNull();
    });

    it('should return null when data is a JSON number', () => {
      const result = parseSSELine('token', '42');

      expect(result).toBeNull();
    });

    it('should return null when data is JSON null', () => {
      const result = parseSSELine('token', 'null');

      expect(result).toBeNull();
    });
  });
});
