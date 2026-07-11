import { describe, expect, it } from 'vitest';
import { parseErrorBody } from '@/utils/parseErrorBody';

describe('parseErrorBody', () => {
  describe('message precedence', () => {
    it('prefers the backend envelope error.message over everything else', () => {
      const body = {
        error: {
          message: 'Envelope wins',
          status_code: 403,
          type: 'auth_error',
        },
        detail: 'detail loses',
        message: 'flat loses',
      };
      expect(parseErrorBody(body, 'Forbidden').message).toBe('Envelope wins');
    });

    it('falls back to FastAPI detail when no envelope is present', () => {
      const body = { detail: 'Project not found', message: 'flat loses' };
      expect(parseErrorBody(body, 'Not Found').message).toBe(
        'Project not found'
      );
    });

    it('falls back to flat message when no envelope or detail is present', () => {
      const body = { message: 'Legacy flat message' };
      expect(parseErrorBody(body, 'Bad Request').message).toBe(
        'Legacy flat message'
      );
    });

    it('falls back to the provided fallback (statusText) when body has no message', () => {
      const body = { something: 'unrelated' };
      expect(parseErrorBody(body, 'Unprocessable Entity').message).toBe(
        'Unprocessable Entity'
      );
    });

    it('uses the last-resort message when neither body nor fallback is usable', () => {
      expect(parseErrorBody({}, undefined).message).toBe('Request failed');
      expect(parseErrorBody(null, undefined).message).toBe('Request failed');
      expect(parseErrorBody(undefined, '').message).toBe('Request failed');
    });

    it('ignores empty / whitespace-only strings at each precedence level', () => {
      const body = {
        error: { message: '   ' },
        detail: '',
        message: 'first real value',
      };
      expect(parseErrorBody(body, 'Server Error').message).toBe(
        'first real value'
      );
    });

    it('treats a plain string body as the message', () => {
      expect(parseErrorBody('raw plaintext error', 'fallback').message).toBe(
        'raw plaintext error'
      );
    });
  });

  describe('error.type surfacing', () => {
    it('surfaces the envelope type so callers can branch on it', () => {
      expect(
        parseErrorBody({
          error: {
            message: 'Rate limited',
            status_code: 429,
            type: 'rate_limit',
          },
        }).type
      ).toBe('rate_limit');

      expect(
        parseErrorBody({
          error: { message: 'No token', status_code: 401, type: 'auth_error' },
        }).type
      ).toBe('auth_error');
    });

    it('omits type when there is no envelope', () => {
      expect(parseErrorBody({ detail: 'x' }).type).toBeUndefined();
      expect(parseErrorBody('plain').type).toBeUndefined();
    });
  });

  describe('additional envelope fields', () => {
    it('surfaces status_code, details and silent from the envelope', () => {
      const parsed = parseErrorBody({
        error: {
          message: 'Validation failed',
          status_code: 422,
          type: 'validation_error',
          details: [{ loc: ['body', 'name'], msg: 'field required' }],
          silent: true,
        },
      });
      expect(parsed.statusCode).toBe(422);
      expect(parsed.details).toEqual([
        { loc: ['body', 'name'], msg: 'field required' },
      ]);
      expect(parsed.silent).toBe(true);
    });

    it('omits optional fields when absent', () => {
      const parsed = parseErrorBody({ error: { message: 'boom' } });
      expect(parsed.statusCode).toBeUndefined();
      expect(parsed.details).toBeUndefined();
      expect(parsed.silent).toBeUndefined();
    });
  });
});
