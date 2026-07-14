/** One paper change emitted by the backend change tracker (serialized ChangeRecord). */
export interface ArxivChangeRecord {
  paper_id: string;
  change_type: 'new' | 'updated' | 'deleted';
  old_hash: string | null;
  new_hash: string;
  change_date: string;
  fields_changed: string[];
  metadata: Record<string, unknown>;
}

export interface TrackResult {
  status: string;
  timestamp: string;
  result: {
    categories: string[];
    period_days: number;
    papers_found: number;
    changes_detected: number;
    changes_by_type: {
      new: ArxivChangeRecord[];
      updated: ArxivChangeRecord[];
      deleted: ArxivChangeRecord[];
    };
    applied: boolean;
    summary: {
      new: number;
      updated: number;
      deleted: number;
      errors: number;
    };
  };
}

export interface StatsResult {
  status: string;
  timestamp: string;
  statistics: {
    total_papers_tracked: number;
    active_papers: number;
    deleted_papers: number;
    categories_tracked: number;
    top_categories: Array<[string, number]>;
    recent_changes_week: Record<string, number>;
  };
}

/** A single extracted feature: either the value, or an error envelope when that feature failed. */
export type ExtractionFeatureError = { error: string };

/** A feature the backend cannot yet produce (e.g. topics, arXiv citations) — reported honestly, not fabricated. */
export type ExtractionFeatureUnsupported = {
  unsupported: string;
  topics?: string[];
  citations?: unknown[];
  references?: unknown[];
  citation_count?: number;
};

export interface ExtractionFeatures {
  entities?: Array<Record<string, unknown>> | ExtractionFeatureError;
  topics?:
    | string[]
    | ExtractionFeatureError
    | ExtractionFeatureUnsupported;
  keyphrases?: string[] | ExtractionFeatureError;
  summary?: string | ExtractionFeatureError;
  citations?:
    | Array<Record<string, unknown>>
    | ExtractionFeatureError
    | ExtractionFeatureUnsupported;
}

/** Per-paper outcome. `partial` = some requested features failed; `failed` = all failed. */
export type ExtractionStatus =
  | 'completed'
  | 'partial'
  | 'failed'
  | (string & {});

export interface ExtractionResult {
  status: string;
  message: string;
  processed_count: number;
  results: Array<{
    paper_id: string;
    title: string;
    extraction_status: ExtractionStatus;
    features: ExtractionFeatures;
    error?: string;
  }>;
}

export interface ArXivPaper {
  id: string;
  title: string;
  authors: string[];
  abstract: string;
  published: string;
  updated: string;
  categories: string[];
  primary_category?: string;
  pdf_url?: string;
}

export interface IngestionResult {
  message: string;
  paper_count: number;
  status: string;
}

export const CORE_AI_CATEGORIES = [
  'cs.AI',
  'cs.LG',
  'cs.CV',
  'cs.CL',
  'stat.ML',
];

export const POPULAR_CATEGORIES = [
  'cs.AI',
  'cs.LG',
  'cs.CV',
  'cs.CL',
  'cs.RO',
  'quant-ph',
  'stat.ML',
  'math.OC',
  'physics.data-an',
  'eess.IV',
];

const ARXIV_ID_PATTERN =
  /^(?:\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[a-z-]+)?\/\d{7}(?:v\d+)?)$/i;

export const normalizePaperIdToken = (value: string) =>
  value
    .trim()
    .replace(/^https?:\/\/arxiv\.org\/abs\//i, '')
    .replace(/^https?:\/\/arxiv\.org\/pdf\//i, '')
    .replace(/\.pdf$/i, '')
    .replace(/^arxiv:/i, '')
    .replace(/\/$/, '');

export const normalizePaperIds = (value: string) =>
  Array.from(
    new Set(
      value
        .split(/[\s,\n]+/)
        .map(normalizePaperIdToken)
        .filter(Boolean)
    )
  );

export const splitValidAndInvalidPaperIds = (value: string) => {
  const validIds: string[] = [];
  const invalidIds: string[] = [];

  normalizePaperIds(value).forEach((id) => {
    if (ARXIV_ID_PATTERN.test(id)) {
      validIds.push(id);
      return;
    }

    invalidIds.push(id);
  });

  return { validIds, invalidIds };
};

export const getErrorMessage = (error: unknown) => {
  if (typeof error !== 'object' || error === null) {
    return 'Request failed. Please retry.';
  }

  const typed = error as {
    response?: { data?: { detail?: string } };
    message?: string;
  };

  if (typed.response?.data?.detail) {
    return typed.response.data.detail;
  }

  if (typed.message) {
    return typed.message;
  }

  return 'Request failed. Please retry.';
};

const getErrorStatusCode = (error: unknown) => {
  if (typeof error !== 'object' || error === null) {
    return null;
  }

  const typed = error as {
    error?: { status_code?: number };
    response?: { status?: number; data?: { error?: { status_code?: number } } };
    message?: string;
  };

  return (
    typed.error?.status_code ??
    typed.response?.data?.error?.status_code ??
    typed.response?.status ??
    null
  );
};

export const getArxivTrackingErrorMessage = (error: unknown) => {
  const rawMessage = getErrorMessage(error);
  const statusCode = getErrorStatusCode(error);
  const normalizedMessage = rawMessage.toLowerCase();

  if (
    statusCode === 429 ||
    statusCode === 503 ||
    normalizedMessage.includes('rate limit') ||
    normalizedMessage.includes('temporarily unavailable') ||
    normalizedMessage.includes('timed out') ||
    normalizedMessage.includes('failed after retries') ||
    normalizedMessage.includes('status code 500')
  ) {
    return 'ArXiv scan failed because the upstream arXiv service is temporarily unavailable or rate limiting requests. Retry in about a minute or scan fewer categories.';
  }

  return rawMessage;
};
