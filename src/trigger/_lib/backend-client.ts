import { logger } from "@trigger.dev/sdk/v3";
import { z } from "zod";

const BACKEND_API_URL = process.env.BACKEND_API_URL ?? "http://localhost:8000";

const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 1000;
const REQUEST_TIMEOUT_MS = 30_000;

export class BackendApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    url: string,
  ) {
    super(`Backend API ${status} from ${url}`);
    this.name = "BackendApiError";
  }
}

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function request<T>(
  method: string,
  path: string,
  options: {
    body?: unknown;
    schema?: z.ZodType<T>;
    headers?: Record<string, string>;
    timeoutMs?: number;
  } = {},
): Promise<T> {
  const url = `${BACKEND_API_URL}${path}`;
  const {
    body,
    schema,
    headers = {},
    timeoutMs = REQUEST_TIMEOUT_MS,
  } = options;

  let lastError: Error | undefined;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    if (attempt > 0) {
      const delay = RETRY_DELAY_MS * Math.pow(2, attempt - 1);
      logger.info(`Retrying ${method} ${path} (attempt ${attempt + 1})`, {
        delay,
      });
      await sleep(delay);
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          ...headers,
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      clearTimeout(timeout);

      if (res.status >= 500 && attempt < MAX_RETRIES) {
        lastError = new BackendApiError(res.status, await res.text(), url);
        continue;
      }

      if (!res.ok) {
        throw new BackendApiError(res.status, await res.text(), url);
      }

      const json = await res.json();
      return schema ? schema.parse(json) : (json as T);
    } catch (err) {
      clearTimeout(timeout);

      if (err instanceof BackendApiError) throw err;

      lastError = err instanceof Error ? err : new Error(String(err));
      if (attempt === MAX_RETRIES) break;
    }
  }

  throw lastError ?? new Error(`Failed after ${MAX_RETRIES + 1} attempts`);
}

function authHeaders(): Record<string, string> {
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!key) return {};
  return { Authorization: `Bearer ${key}` };
}

export const backendClient = {
  get<T>(
    path: string,
    schema?: z.ZodType<T>,
    extraHeaders?: Record<string, string>,
  ) {
    return request<T>("GET", path, {
      schema,
      headers: { ...authHeaders(), ...extraHeaders },
    });
  },

  post<T>(
    path: string,
    body: unknown,
    schema?: z.ZodType<T>,
    extraHeaders?: Record<string, string>,
  ) {
    return request<T>("POST", path, {
      body,
      schema,
      headers: { ...authHeaders(), ...extraHeaders },
    });
  },

  healthCheck() {
    return request("GET", "/health");
  },
};
