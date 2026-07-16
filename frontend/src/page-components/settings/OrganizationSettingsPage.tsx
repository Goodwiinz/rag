import type { ReactElement } from 'react';
import Link from 'next/link';
import { ArrowRight, BriefcaseBusiness } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';

type OrganizationArea = {
  title: string;
  description: string;
  /**
   * A real, reachable management surface. When null, the area is not built
   * yet and we show an honest "not available" note instead of a dead link.
   */
  href: string | null;
  /** Honest copy when no data source or sub-route exists yet. */
  emptyNote: string;
};

const ORGANIZATION_AREAS: OrganizationArea[] = [
  {
    title: 'Members and roles',
    description:
      'Invite people to the workspace and set who can read, edit, and administer.',
    href: null,
    emptyNote: 'Membership management is not connected yet.',
  },
  {
    title: 'Usage and billing',
    description:
      'See document capacity, credit consumption, and the next plan reset.',
    href: null,
    emptyNote: 'No usage data yet. Billing is not connected to this workspace.',
  },
  {
    title: 'Developer access',
    description:
      'Manage API tokens and provider access for models and integrations.',
    href: '/settings/api-keys',
    emptyNote: '',
  },
];

export const OrganizationSettingsPage = (): ReactElement => {
  return (
    <div className="space-y-8 px-6 pb-20 pt-6 md:space-y-10 md:px-10 md:pb-24 md:pt-8 lg:px-12">
      <header className="space-y-6">
        <div className="space-y-3">
          <h1 className="text-3xl font-semibold text-[var(--nous-fg-1)]">
            Organization Settings
          </h1>
          <p className="max-w-3xl text-sm text-[var(--nous-fg-2)]">
            Manage workspace identity, access, and developer settings for NOUS.
          </p>
        </div>

        <Button
          asChild
          variant="outline"
          className="border-[var(--nous-border-1)] bg-transparent text-[var(--nous-fg-1)] hover:bg-[var(--nous-bg-1)] hover:text-[var(--nous-fg-1)] focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
        >
          <Link href="/settings">
            <ArrowRight className="h-4 w-4 rotate-180" aria-hidden="true" />
            Back to settings
          </Link>
        </Button>
      </header>

      <Card className="rounded-2xl border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-none">
        <CardContent className="flex flex-col gap-4 p-6 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-1)] text-[var(--nous-sol)]">
              <BriefcaseBusiness className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="space-y-1">
              <p className="text-base font-medium text-[var(--nous-fg-1)]">
                Default research workspace
              </p>
              <p className="text-sm text-[var(--nous-fg-2)]">
                The active workspace for research, ingestion, and access
                control.
              </p>
            </div>
          </div>
          <Badge
            variant="outline"
            className="self-start border-[var(--nous-border-1)] bg-[var(--nous-bg-1)] text-[var(--nous-fg-2)] md:self-center"
          >
            Active workspace
          </Badge>
        </CardContent>
      </Card>

      <section
        aria-labelledby="organization-areas-heading"
        className="space-y-4"
      >
        <h2
          id="organization-areas-heading"
          className="text-lg font-semibold text-[var(--nous-fg-1)]"
        >
          Manage
        </h2>
        <ul className="space-y-3">
          {ORGANIZATION_AREAS.map((area) => {
            const isAvailable = area.href !== null;

            const body = (
              <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1.5">
                  <p className="text-base font-medium text-[var(--nous-fg-1)]">
                    {area.title}
                  </p>
                  <p className="max-w-2xl text-sm text-[var(--nous-fg-2)]">
                    {area.description}
                  </p>
                  {!isAvailable && (
                    <p className="text-sm text-[var(--nous-fg-3)]">
                      {area.emptyNote}
                    </p>
                  )}
                </div>
                {isAvailable ? (
                  <span className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--nous-sol)]">
                    Open
                    <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </span>
                ) : (
                  <Badge
                    variant="outline"
                    className="self-start border-[var(--nous-border-1)] bg-[var(--nous-bg-1)] text-[var(--nous-fg-3)]"
                  >
                    Not available yet
                  </Badge>
                )}
              </div>
            );

            return (
              <li key={area.title}>
                {isAvailable && area.href ? (
                  <Card
                    interactive
                    className="rounded-2xl border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-none"
                  >
                    <Link
                      href={area.href}
                      aria-label={`Open ${area.title.toLowerCase()}`}
                      className="block rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
                    >
                      {body}
                    </Link>
                  </Card>
                ) : (
                  <Card className="rounded-2xl border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-none">
                    {body}
                  </Card>
                )}
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
};

export default OrganizationSettingsPage;
