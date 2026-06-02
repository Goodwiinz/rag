import type { ReactElement } from 'react';
import Link from 'next/link';
import { ArrowRight, KeyRound, RotateCw, ServerCog } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const API_ACCESS_CARDS = [
  {
    title: 'Active Tokens',
    description:
      'Personal and workspace-scoped credentials currently available to operators and systems.',
    details: [
      '2 active personal tokens',
      '1 workspace-scoped token',
      'Last rotation 9 days ago',
    ],
    icon: KeyRound,
  },
  {
    title: 'Provider Access',
    description:
      'Visibility into configured AI providers and external integration readiness.',
    details: [
      'OpenAI available',
      'Anthropic available',
      'Azure OpenAI pending review',
    ],
    icon: ServerCog,
  },
  {
    title: 'Rotation Guidance',
    description:
      'Operational guidance for token naming, scope minimization, and regular refresh cadence.',
    details: [
      'Use least-privilege scopes',
      'Rotate quarterly',
      'Track token ownership',
    ],
    icon: RotateCw,
  },
] as const;

export const APIKeyManagementPage = (): ReactElement => {
  return (
    <div className="space-y-8 px-6 pb-20 pt-6 md:space-y-10 md:px-10 md:pb-24 md:pt-8 lg:px-12">
      <header className="space-y-4">
        <div className="space-y-2">
          <p className="text-xs font-mono uppercase tracking-[0.28em] text-[var(--nous-sol)]">
            DEVELOPER_ACCESS
          </p>
          <div className="space-y-3">
            <h1 className="text-3xl font-semibold text-[var(--nous-fg-1)]">
              API Key Management
            </h1>
            <p className="max-w-3xl text-sm text-[var(--nous-fg-3)]">
              Review credentials, provider readiness, and token hygiene for
              model and integration access.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button
            asChild
            variant="outline"
            className="border-[var(--nous-border-1)] bg-transparent text-[var(--nous-fg-1)] hover:bg-[var(--nous-bg-1)] hover:text-[var(--nous-fg-1)]"
          >
            <Link href="/settings">
              Return to Settings Overview
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
          <Button
            variant="outline"
            className="border-[var(--nous-border-1)] bg-transparent text-[var(--nous-fg-1)] hover:bg-[var(--nous-bg-1)] hover:text-[var(--nous-fg-1)]"
          >
            Create Token
          </Button>
        </div>
      </header>

      <section className="grid gap-4 lg:grid-cols-3">
        {API_ACCESS_CARDS.map((card) => {
          const Icon = card.icon;

          return (
            <Card
              key={card.title}
              className="rounded-2xl border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-none"
            >
              <CardHeader className="space-y-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--nous-sol-glow)] text-[var(--nous-sol)]">
                  <Icon className="h-5 w-5" />
                </div>
                <div className="space-y-2">
                  <CardTitle className="text-xl text-[var(--nous-fg-1)]">
                    {card.title}
                  </CardTitle>
                  <p className="text-sm text-[var(--nous-fg-3)]">
                    {card.description}
                  </p>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {card.details.map((detail) => (
                  <p
                    key={detail}
                    className="text-sm text-[var(--nous-fg-1)]"
                  >
                    {detail}
                  </p>
                ))}
              </CardContent>
            </Card>
          );
        })}
      </section>
    </div>
  );
};

export default APIKeyManagementPage;
