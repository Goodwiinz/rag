import type { ReactElement } from 'react';
import Link from 'next/link';
import {
  ArrowRight,
  BriefcaseBusiness,
  CreditCard,
  ShieldCheck,
  Users,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const ORGANIZATION_CARDS = [
  {
    title: 'Members & roles',
    description:
      'Manage who can access this workspace and the role boundaries that govern research operations.',
    points: [
      'Invite and remove members',
      'Assign admin coverage',
      'Role-based access control',
    ],
    href: '/settings',
    icon: Users,
  },
  {
    title: 'Usage & billing',
    description:
      'Review document capacity, compute consumption, and your upcoming plan reset window.',
    points: [
      'Track indexed storage',
      'Monitor credit consumption',
      'View plan renewal date',
    ],
    href: '/settings',
    icon: CreditCard,
  },
  {
    title: 'Security & compliance',
    description:
      'Check audit visibility, encryption posture, and administrative control readiness.',
    points: [
      'Audit event history',
      'Encryption at rest',
      'Human-in-the-loop controls',
    ],
    href: '/settings',
    icon: ShieldCheck,
  },
] as const;

export const OrganizationSettingsPage = (): ReactElement => {
  return (
    <div className="min-h-screen bg-background">
      <div className="space-y-8 px-6 pb-20 pt-6 md:space-y-10 md:px-10 md:pb-24 md:pt-8 lg:px-12">
        <header className="space-y-4">
          <div className="space-y-3">
            <h1 className="text-2xl font-semibold text-foreground">
              Organization settings
            </h1>
            <p className="max-w-3xl text-sm text-muted-foreground">
              Configure workspace identity, access governance, and operating
              controls for your NOUS workspace.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button asChild variant="outline">
              <Link href="/settings">
                Back to settings
                <ArrowRight aria-hidden="true" className="h-4 w-4" />
              </Link>
            </Button>
            <Button asChild>
              <Link href="/settings/api-keys">
                Review developer access
                <ArrowRight aria-hidden="true" className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </header>

        <Card>
          <CardContent className="flex flex-col gap-4 p-6 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <BriefcaseBusiness aria-hidden="true" className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">
                  Default research workspace
                </p>
                <p className="text-sm text-muted-foreground">
                  Tenant-aligned workspace for research, ingestion, and
                  governance.
                </p>
              </div>
            </div>
            <span className="inline-flex items-center gap-2 self-start rounded-lg border border-primary/30 bg-primary/5 px-3 py-1.5 text-xs font-medium text-primary md:self-auto">
              <span
                aria-hidden="true"
                className="inline-flex h-2 w-2 rounded-full bg-primary"
              />
              Policy posture: stable
            </span>
          </CardContent>
        </Card>

        <section className="grid gap-4 lg:grid-cols-3">
          {ORGANIZATION_CARDS.map((card) => {
            const Icon = card.icon;

            return (
              <Link
                key={card.title}
                href={card.href}
                className="group rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <Card interactive className="h-full">
                  <CardHeader className="space-y-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <Icon aria-hidden="true" className="h-5 w-5" />
                    </div>
                    <div className="space-y-2">
                      <CardTitle className="flex items-center justify-between text-lg text-foreground">
                        {card.title}
                        <ArrowRight
                          aria-hidden="true"
                          className="h-4 w-4 text-muted-foreground transition-all group-hover:translate-x-0.5 group-hover:text-primary"
                        />
                      </CardTitle>
                      <p className="text-sm text-muted-foreground">
                        {card.description}
                      </p>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {card.points.map((point) => (
                        <li
                          key={point}
                          className="flex items-start gap-2 text-sm text-foreground"
                        >
                          <span
                            aria-hidden="true"
                            className="mt-2 h-1 w-1 shrink-0 rounded-full bg-primary/60"
                          />
                          {point}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </section>
      </div>
    </div>
  );
};

export default OrganizationSettingsPage;
