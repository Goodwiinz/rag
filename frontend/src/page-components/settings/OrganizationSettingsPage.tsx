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
    title: 'Members & Roles',
    description:
      'Manage workspace membership, admin coverage, and role boundaries for research operations.',
    details: ['12 active members', '4 admins', 'RBAC enforced'],
    icon: Users,
  },
  {
    title: 'Usage & Billing',
    description:
      'Track document capacity, compute consumption, and upcoming plan reset windows.',
    details: [
      '428 credits remaining',
      '2.3 TB indexed storage',
      'Renews April 17',
    ],
    icon: CreditCard,
  },
  {
    title: 'Security & Compliance',
    description:
      'Review audit visibility, encryption posture, and administrative control readiness.',
    details: [
      'Audit events available',
      'Encryption enabled',
      'HITL controls ready',
    ],
    icon: ShieldCheck,
  },
] as const;

export const OrganizationSettingsPage = (): ReactElement => {
  return (
    <div className="space-y-8 px-6 pb-20 pt-6 md:space-y-10 md:px-10 md:pb-24 md:pt-8 lg:px-12">
      <header className="space-y-4">
        <div className="space-y-2">
          <p className="text-xs font-mono uppercase tracking-[0.28em] text-[var(--phosphor-green)]">
            WORKSPACE_GOVERNANCE
          </p>
          <div className="space-y-3">
            <h1 className="text-3xl font-semibold text-[var(--terminal-text)]">
              Organization Settings
            </h1>
            <p className="max-w-3xl text-sm text-[var(--terminal-text-dim)]">
              Configure workspace identity, access governance, and operating
              controls for the NOUS platform.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button
            asChild
            variant="outline"
            className="border-[var(--terminal-border)] bg-transparent text-[var(--terminal-text)] hover:bg-[var(--terminal-bg)] hover:text-[var(--terminal-text)]"
          >
            <Link href="/settings">
              Return to Settings Overview
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
          <Button asChild>
            <Link href="/settings/api-keys">
              Review Developer Access
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </header>

      <Card className="rounded-2xl border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-none">
        <CardContent className="flex flex-col gap-4 p-6 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-[var(--terminal-text)]">
              Default Research Workspace
            </p>
            <p className="text-sm text-[var(--terminal-text-dim)]">
              Tenant-aligned workspace for research, ingestion, and governance.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-[var(--terminal-border)] bg-[var(--terminal-bg)] px-4 py-2 text-sm text-[var(--terminal-text)]">
            <BriefcaseBusiness className="h-4 w-4 text-[var(--phosphor-green)]" />
            Workspace policy posture: Stable
          </div>
        </CardContent>
      </Card>

      <section className="grid gap-4 lg:grid-cols-3">
        {ORGANIZATION_CARDS.map((card) => {
          const Icon = card.icon;

          return (
            <Card
              key={card.title}
              className="rounded-2xl border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-none"
            >
              <CardHeader className="space-y-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--phosphor-green-glow)] text-[var(--phosphor-green)]">
                  <Icon className="h-5 w-5" />
                </div>
                <div className="space-y-2">
                  <CardTitle className="text-xl text-[var(--terminal-text)]">
                    {card.title}
                  </CardTitle>
                  <p className="text-sm text-[var(--terminal-text-dim)]">
                    {card.description}
                  </p>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {card.details.map((detail) => (
                  <p
                    key={detail}
                    className="text-sm text-[var(--terminal-text)]"
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

export default OrganizationSettingsPage;
