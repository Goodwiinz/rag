import type { ReactElement } from 'react';
import Link from 'next/link';
import { ArrowRight, KeyRound, RotateCw, ServerCog } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const API_ACCESS_CARDS = [
  {
    title: 'Active tokens',
    description:
      'Personal and workspace-scoped credentials currently available to operators and systems.',
    details: [
      'Personal tokens are listed here once created',
      'Workspace-scoped tokens appear under your workspace',
      'Each token shows its last rotation date',
    ],
    icon: KeyRound,
  },
  {
    title: 'Provider access',
    description:
      'Visibility into configured AI providers and external integration readiness.',
    details: [
      'OpenAI connects through your provider key',
      'Anthropic connects through your provider key',
      'Azure OpenAI requires workspace review',
    ],
    icon: ServerCog,
  },
  {
    title: 'Rotation guidance',
    description:
      'Operational guidance for token naming, scope minimization, and a regular refresh cadence.',
    details: [
      'Use least-privilege scopes',
      'Rotate keys quarterly',
      'Track token ownership',
    ],
    icon: RotateCw,
  },
] as const;

export const APIKeyManagementPage = (): ReactElement => {
  return (
    <div className="space-y-8 px-6 pb-20 pt-6 md:space-y-10 md:px-10 md:pb-24 md:pt-8 lg:px-12">
      <header className="space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <KeyRound aria-hidden="true" className="h-6 w-6" />
            </div>
            <div className="space-y-1.5">
              <h1 className="text-2xl font-semibold text-foreground">
                API keys
              </h1>
              <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
                Review credentials, provider readiness, and token hygiene for
                model and integration access.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button asChild variant="outline">
              <Link href="/settings">
                Back to settings
                <ArrowRight aria-hidden="true" className="h-4 w-4" />
              </Link>
            </Button>
            <Button>Create token</Button>
          </div>
        </div>
      </header>

      <section className="grid gap-4 lg:grid-cols-3">
        {API_ACCESS_CARDS.map((card) => {
          const Icon = card.icon;

          return (
            <Card key={card.title} className="flex flex-col">
              <CardHeader className="space-y-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-primary">
                  <Icon aria-hidden="true" className="h-5 w-5" />
                </div>
                <div className="space-y-2">
                  <CardTitle className="text-lg text-foreground">
                    {card.title}
                  </CardTitle>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {card.description}
                  </p>
                </div>
              </CardHeader>
              <CardContent className="mt-auto">
                <ul className="space-y-2 border-t border-border pt-4">
                  {card.details.map((detail) => (
                    <li
                      key={detail}
                      className="flex items-start gap-2.5 text-sm text-foreground"
                    >
                      <span
                        aria-hidden="true"
                        className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/60"
                      />
                      <span className="leading-relaxed">{detail}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          );
        })}
      </section>
    </div>
  );
};

export default APIKeyManagementPage;
