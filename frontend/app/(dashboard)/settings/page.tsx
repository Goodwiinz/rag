'use client';

import Link from 'next/link';
import { useState, type ComponentType, type ReactElement } from 'react';
import {
  ArrowRight,
  BadgeCheck,
  Bell,
  BriefcaseBusiness,
  Clock3,
  CreditCard,
  KeyRound,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  UserCog,
  UserCircle2,
  Workflow,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import { useAuth } from '@/hooks/useAuth';

type PreferenceKey =
  | 'compactMode'
  | 'emailNotifications'
  | 'desktopNotifications';

type SettingsStatusItem = {
  label: string;
  value: string;
  hint: string;
  icon: ComponentType<{ className?: string }>;
};

type SettingsCardItem = {
  title: string;
  description: string;
  summary: string;
  href: string;
  cta: string;
  icon: ComponentType<{ className?: string }>;
  accent: string;
};

const STATUS_ITEMS: SettingsStatusItem[] = [
  {
    label: 'Workspace',
    value: 'Default Research Workspace',
    hint: 'Active tenant context',
    icon: BriefcaseBusiness,
  },
  {
    label: 'Role',
    value: 'Admin',
    hint: 'Full governance access',
    icon: UserCog,
  },
  {
    label: 'Plan',
    value: 'Research Pro',
    hint: '428 credits remain this cycle',
    icon: Sparkles,
  },
  {
    label: 'Security',
    value: 'Protected',
    hint: 'Audit and encryption active',
    icon: ShieldCheck,
  },
  {
    label: 'API Access',
    value: '2 tokens',
    hint: 'OpenAI and Anthropic ready',
    icon: KeyRound,
  },
];

const SETTINGS_CARDS: SettingsCardItem[] = [
  {
    title: 'Profile & Preferences',
    description: 'Identity, timezone, display defaults, and notification tone.',
    summary:
      'Primary email, profile defaults, and personal workspace behavior.',
    href: '#personal-preferences',
    cta: 'Jump to personal controls',
    icon: UserCircle2,
    accent: 'bg-[var(--phosphor-green-glow)] text-[var(--phosphor-green)]',
  },
  {
    title: 'Workspace & Access',
    description: 'Tenant identity, members, roles, and collaboration controls.',
    summary: 'Manage workspace context, membership, and administrative access.',
    href: '/settings/organization',
    cta: 'Open Workspace & Access',
    icon: BriefcaseBusiness,
    accent: 'bg-sky-500/10 text-sky-400',
  },
  {
    title: 'Security & Compliance',
    description:
      'Authentication posture, audit controls, and policy readiness.',
    summary:
      'Review session protection, audit posture, and governance controls.',
    href: '/settings/organization',
    cta: 'Open Security & Compliance',
    icon: ShieldCheck,
    accent: 'bg-emerald-500/10 text-emerald-400',
  },
  {
    title: 'Usage & Billing',
    description: 'Plan tier, compute consumption, storage, and renewal timing.',
    summary: 'Track credits, document capacity, and billing visibility.',
    href: '/settings/organization',
    cta: 'Open Usage & Billing',
    icon: CreditCard,
    accent: 'bg-amber-500/10 text-amber-400',
  },
  {
    title: 'Developer Access',
    description: 'Token inventory, provider readiness, and scope visibility.',
    summary: 'Manage API access, token rotation, and developer credentials.',
    href: '/settings/api-keys',
    cta: 'Open Developer Access',
    icon: KeyRound,
    accent: 'bg-violet-500/10 text-violet-400',
  },
  {
    title: 'Connected Systems',
    description: 'Provider connectivity and external integration readiness.',
    summary: 'See which model and integration surfaces are ready to use.',
    href: '/settings/api-keys',
    cta: 'Open Connected Systems',
    icon: Workflow,
    accent: 'bg-cyan-500/10 text-cyan-400',
  },
];

const PREFERENCE_ITEMS = [
  {
    key: 'compactMode',
    label: 'Compact mode',
    description: 'Reduce whitespace in dense research and admin workflows.',
  },
  {
    key: 'emailNotifications',
    label: 'Email notifications',
    description: 'Receive workspace alerts, summaries, and access updates.',
  },
  {
    key: 'desktopNotifications',
    label: 'Desktop notifications',
    description:
      'Show local prompts for live runs, incidents, and completed jobs.',
  },
] as const;

const TRUST_ITEMS = ['Audit active', 'Encrypted', 'Admin access'];

export default function SettingsPage(): ReactElement {
  const { user } = useAuth();
  const [preferences, setPreferences] = useState({
    compactMode: false,
    emailNotifications: true,
    desktopNotifications: true,
  });

  const primaryEmail = user?.email ?? 'Not provided';
  const operatorName =
    primaryEmail === 'Not provided' ? 'Operator' : primaryEmail.split('@')[0];
  const operatorInitial = operatorName.charAt(0).toUpperCase();

  const togglePreference = (key: PreferenceKey, checked: boolean): void => {
    setPreferences((current) => ({
      ...current,
      [key]: checked,
    }));
  };

  return (
    <div className="space-y-8 px-6 pb-20 pt-6 md:space-y-10 md:px-10 md:pb-24 md:pt-8 lg:px-12">
      <header className="space-y-3">
        <div className="space-y-3">
          <h1 className="text-3xl font-semibold text-[var(--terminal-text)]">
            Settings
          </h1>
          <p className="max-w-3xl text-sm text-[var(--terminal-text-dim)]">
            Manage your account, workspace governance, model access, and
            platform controls.
          </p>
        </div>

        <Card className="overflow-hidden rounded-2xl border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-none">
          <CardContent className="grid gap-4 p-5 sm:p-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
            <div className="flex items-start gap-3">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-[var(--terminal-border)] bg-[linear-gradient(180deg,rgba(212,160,57,0.16),rgba(212,160,57,0.04))] text-lg font-semibold text-[var(--terminal-text)]">
                {operatorInitial}
              </div>
              <div className="space-y-2">
                <div className="space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-lg font-semibold text-[var(--terminal-text)]">
                      {operatorName}
                    </p>
                    <span className="inline-flex items-center rounded-full border border-[var(--terminal-border)] bg-[var(--terminal-bg)] px-2.5 py-1 text-xs font-medium text-[var(--terminal-text)]">
                      Administrator
                    </span>
                  </div>
                  <p className="text-sm text-[var(--terminal-text-dim)]">
                    {primaryEmail}
                  </p>
                </div>
              </div>
            </div>

            <div className="grid gap-3 rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)] p-3.5 sm:p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1">
                  <p className="text-xs font-mono uppercase tracking-[0.2em] text-[var(--terminal-text-dim)]">
                    Last sign-in
                  </p>
                  <div className="flex items-center gap-2 text-sm text-[var(--terminal-text)]">
                    <Clock3 className="h-4 w-4 text-[var(--phosphor-green)]" />
                    Today at 09:10
                  </div>
                </div>
                <div className="space-y-1">
                  <p className="text-xs font-mono uppercase tracking-[0.2em] text-[var(--terminal-text-dim)]">
                    Session trust
                  </p>
                  <div className="flex items-center gap-2 text-sm text-[var(--terminal-text)]">
                    <BadgeCheck className="h-4 w-4 text-[var(--phosphor-green)]" />
                    Verified operator context
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {TRUST_ITEMS.map((item) => (
                  <span
                    key={item}
                    className="inline-flex items-center rounded-full border border-[var(--terminal-border)] bg-[var(--terminal-surface)] px-3 py-1 text-xs font-medium text-[var(--terminal-text)]"
                  >
                    {item}
                  </span>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </header>

      <section className="space-y-3" aria-labelledby="settings-status-title">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-[var(--phosphor-green)]" />
          <h2
            id="settings-status-title"
            className="text-sm font-mono uppercase tracking-[0.24em] text-[var(--phosphor-green)]"
          >
            OPERATING_STATUS
          </h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {STATUS_ITEMS.map((item) => {
            const Icon = item.icon;

            return (
              <Card
                key={item.label}
                className="rounded-2xl border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-none"
              >
                <CardContent className="space-y-2 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--terminal-bg)] text-[var(--phosphor-green)]">
                        <Icon className="h-4 w-4" />
                      </div>
                      <p className="text-xs font-mono uppercase tracking-[0.24em] text-[var(--terminal-text-dim)]">
                        {item.label}
                      </p>
                    </div>
                    <span className="h-2 w-2 rounded-full bg-[var(--phosphor-green)]" />
                  </div>
                  <p className="text-xl font-semibold leading-tight text-[var(--terminal-text)]">
                    {item.value}
                  </p>
                  <p className="text-sm text-[var(--terminal-text-dim)]">
                    {item.hint}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      <section className="space-y-3" aria-labelledby="settings-areas-title">
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4 text-[var(--phosphor-green)]" />
          <h2
            id="settings-areas-title"
            className="text-sm font-mono uppercase tracking-[0.24em] text-[var(--phosphor-green)]"
          >
            SETTINGS_AREAS
          </h2>
        </div>
        <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
          {SETTINGS_CARDS.map((item) => {
            const Icon = item.icon;
            const actionClassName =
              'inline-flex items-center gap-2 text-sm font-medium text-[var(--terminal-text)] transition-colors hover:text-[var(--phosphor-green)]';
            const actionContent = (
              <>
                {item.cta}
                <ArrowRight className="h-4 w-4" />
              </>
            );

            return (
              <Card
                key={item.title}
                className="rounded-2xl border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-none"
              >
                <CardHeader className="space-y-3 p-5 pb-2">
                  <div className="flex items-center justify-between gap-3">
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-xl ${item.accent}`}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <CardTitle className="text-xl text-[var(--terminal-text)]">
                      {item.title}
                    </CardTitle>
                    <p className="text-sm leading-6 text-[var(--terminal-text-dim)]">
                      {item.description}
                    </p>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3 p-5 pt-0">
                  <p className="text-sm leading-6 text-[var(--terminal-text)]">
                    {item.summary}
                  </p>
                  <div className="border-t border-[var(--terminal-border)] pt-2">
                    {item.href.startsWith('#') ? (
                      <a href={item.href} className={actionClassName}>
                        {actionContent}
                      </a>
                    ) : (
                      <Link href={item.href} className={actionClassName}>
                        {actionContent}
                      </Link>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      <section
        id="personal-preferences"
        className="scroll-mt-24"
        aria-labelledby="personal-preferences-title"
      >
        <Card className="rounded-2xl border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-none">
          <CardHeader className="space-y-2 p-5 pb-2">
            <div className="flex items-center gap-2">
              <Bell className="h-4 w-4 text-[var(--phosphor-green)]" />
              <p className="text-xs font-mono uppercase tracking-[0.24em] text-[var(--phosphor-green)]">
                PERSONAL_CONTROLS
              </p>
            </div>
            <div className="space-y-2">
              <CardTitle
                id="personal-preferences-title"
                className="text-2xl text-[var(--terminal-text)]"
              >
                Personal Preferences
              </CardTitle>
              <p className="max-w-3xl text-sm text-[var(--terminal-text-dim)]">
                Keep quick personal defaults on the overview page. These
                controls stay local in this pass and do not write to backend
                settings yet.
              </p>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 p-5 pt-0">
            {PREFERENCE_ITEMS.map((item, index) => (
              <div key={item.key} className="space-y-4">
                {index > 0 && (
                  <Separator className="bg-[var(--terminal-border)]" />
                )}
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="space-y-1">
                    <Label
                      htmlFor={item.key}
                      className="text-sm font-medium text-[var(--terminal-text)]"
                    >
                      {item.label}
                    </Label>
                    <p className="text-sm text-[var(--terminal-text-dim)]">
                      {item.description}
                    </p>
                  </div>
                  <Switch
                    id={item.key}
                    checked={preferences[item.key]}
                    onCheckedChange={(checked) =>
                      togglePreference(item.key, checked)
                    }
                  />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
