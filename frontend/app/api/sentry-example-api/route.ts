import { NextResponse } from 'next/server';

class SentryExampleAPIError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'SentryExampleAPIError';
  }
}

export const dynamic = 'force-dynamic';

export function GET() {
  throw new SentryExampleAPIError(
    'This error is raised on the backend called by the example page.'
  );
  return NextResponse.json({ data: 'Testing Sentry Error...' });
}
