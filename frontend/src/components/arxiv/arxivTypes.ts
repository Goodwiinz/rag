export interface TrackResult {
  status: string;
  timestamp: string;
  result: {
    categories: string[];
    period_days: number;
    papers_found: number;
    changes_detected: number;
    changes_by_type: {
      new: Array<any>;
      updated: Array<any>;
      deleted: Array<any>;
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
    recent_changes_week: any;
    state_file_path: string;
  };
}

export interface ExtractionResult {
  status: string;
  message: string;
  processed_count: number;
  results: Array<{
    paper_id: string;
    title: string;
    extraction_status: string;
    features: {
      entities?: any;
      topics?: string[] | { error: string };
      keyphrases?: string[] | { error: string };
      summary?: string | { error: string };
      citations?: any;
    };
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
