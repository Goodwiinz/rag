import type { ReactElement } from 'react';
import Link from 'next/link';
import { ArrowLeft, KeyRound, Plug, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const ROTATION_GUIDANCE = [
  'Scope each key to the least access it needs.',
  'Rotate keys on a regular schedule and after any suspected exposure.',
  'Give every key an owner and a clear name so it can be traced.',
] as const;

export const APIKeyManagementPage = (): ReactElement => {
  return (
    <div className="space-y-8 px-6 pb-16 pt-6 md:space-y-10 md:px-10 md:pt-8 lg:px-12">
      <header className="space-y-4">
        <Link
          href="/settings"
          className="inline-flex items-center gap-1.5 rounded-md text-sm text-[var(--nous-fg-3)] transition-colors hover:text-[var(--nous-fg-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to settings
        </Link>

        <div className="space-y-2">
          <p className="nous-overline">Settings</p>
          <h1 className="text-3xl font-semibold text-[var(--nous-fg-1)]">
            API keys
          </h1>
          <p className="max-w-2xl text-sm text-[var(--nous-fg-3)]">
            Personal and workspace keys you can use to call the model and
            integration APIs.
          </p>
        </div>
      </header>

      <section aria-labelledby="api-keys-heading" className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2
            id="api-keys-heading"
            className="text-lg font-semibold text-[var(--nous-fg-1)]"
          >
            Your keys
          </h2>
          <Button variant="accent" disabled>
            Create key
          </Button>
        </div>

        <Card className="rounded-2xl border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-none">
          <CardContent className="flex flex-col items-center gap-3 px-6 py-14 text-center">
            <div
              className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--nous-sol-glow)] text-[var(--nous-sol)]"
              aria-hidden="true"
            >
              <KeyRound className="h-6 w-6" />
            </div>
            <div className="space-y-1.5">
              <p className="text-base font-medium text-[var(--nous-fg-1)]">
                No API keys yet
              </p>
              <p className="max-w-md text-sm text-[var(--nous-fg-3)]">
                Key creation is not available in this build yet. When it is,
                your keys will appear here with their name, scope, and last use.
              </p>
            </div>
          </CardContent>
        </Card>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section aria-labelledby="providers-heading" className="space-y-3">
          <h2
            id="providers-heading"
            className="text-lg font-semibold text-[var(--nous-fg-1)]"
          >
            Provider access
          </h2>
          <Card className="h-full rounded-2xl border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-none">
            <CardContent className="flex flex-col items-center gap-3 px-6 py-12 text-center">
              <div
                className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--nous-sol-glow)] text-[var(--nous-sol)]"
                aria-hidden="true"
              >
                <Plug className="h-5 w-5" />
              </div>
              <div className="space-y-1.5">
                <p className="text-base font-medium text-[var(--nous-fg-1)]">
                  No providers connected
                </p>
                <p className="max-w-sm text-sm text-[var(--nous-fg-3)]">
                  Connect a workspace to see which model providers are available
                  and their readiness.
                </p>
              </div>
            </CardContent>
          </Card>
        </section>

        <section aria-labelledby="guidance-heading" className="space-y-3">
          <h2
            id="guidance-heading"
            className="text-lg font-semibold text-[var(--nous-fg-1)]"
          >
            Keeping keys safe
          </h2>
          <Card className="h-full rounded-2xl border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-none">
            <CardHeader className="flex-row items-center gap-3 space-y-0 pb-2">
              <div
                className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--nous-sol-glow)] text-[var(--nous-sol)]"
                aria-hidden="true"
              >
                <ShieldCheck className="h-5 w-5" />
              </div>
              <CardTitle className="text-base text-[var(--nous-fg-1)]">
                A few habits worth keeping
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2.5">
                {ROTATION_GUIDANCE.map((item) => (
                  <li
                    key={item}
                    className="flex gap-2.5 text-sm text-[var(--nous-fg-2)]"
                  >
                    <span
                      className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--nous-sol)]"
                      aria-hidden="true"
                    />
                    {item}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
};

export default APIKeyManagementPage;
