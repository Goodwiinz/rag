'use client';

import * as Sentry from '@sentry/nextjs';
import { useState } from 'react';

class SentryExampleFrontendError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'SentryExampleFrontendError';
  }
}

export default function SentryExamplePage() {
  const [hasSentError, setHasSentError] = useState(false);
  const [isConnected, setIsConnected] = useState(true);

  return (
    <main
      style={{
        fontFamily: 'system-ui, sans-serif',
        maxWidth: 640,
        margin: '4rem auto',
        padding: '0 1.5rem',
        lineHeight: 1.5,
      }}
    >
      <h1 style={{ fontSize: '2rem', marginBottom: '1rem' }}>
        sentry-example-page
      </h1>
      <p style={{ marginBottom: '1.5rem' }}>
        Click the button below, and view the sample error on the{' '}
        <a
          href="https://goodwiinz-uk.sentry.io/issues/?project=nous-frontend"
          target="_blank"
          rel="noreferrer"
          style={{ color: '#D4A039', textDecoration: 'underline' }}
        >
          Sentry Issues page
        </a>
        . For more details about setting up Sentry,{' '}
        <a
          href="https://docs.sentry.io/platforms/javascript/guides/nextjs/"
          target="_blank"
          rel="noreferrer"
          style={{ color: '#D4A039', textDecoration: 'underline' }}
        >
          read the docs
        </a>
        .
      </p>

      <button
        type="button"
        onClick={async () => {
          await Sentry.startSpan(
            {
              name: 'Example Frontend Span',
              op: 'test',
            },
            async () => {
              try {
                const res = await fetch('/api/sentry-example-api');
                if (!res.ok) {
                  setHasSentError(true);
                }
              } catch {
                setIsConnected(false);
              }
              throw new SentryExampleFrontendError(
                'This error is raised on the frontend of the example page.'
              );
            }
          );
        }}
        style={{
          background: '#D4A039',
          color: '#0A0A0E',
          border: 'none',
          borderRadius: 6,
          padding: '0.75rem 1.5rem',
          fontSize: '1rem',
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        Throw Sample Error
      </button>

      {hasSentError ? (
        <p style={{ marginTop: '1.5rem', color: '#16a34a' }}>
          Sample error was sent to Sentry.
        </p>
      ) : !isConnected ? (
        <div
          style={{
            marginTop: '1.5rem',
            padding: '1rem',
            background: '#fef3c7',
            border: '1px solid #f59e0b',
            borderRadius: 6,
            color: '#92400e',
          }}
        >
          The Sentry SDK is not transmitting events. Check that the tunnel route
          at <code>/monitoring</code> is reachable and that{' '}
          <code>NEXT_PUBLIC_SENTRY_DSN</code> is set at build time.
        </div>
      ) : null}
    </main>
  );
}
