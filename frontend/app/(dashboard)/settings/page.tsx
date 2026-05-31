'use client';

import Link from 'next/link';
import { useState, type ComponentType, type ReactElement } from 'react';
import { motion, MotionConfig } from 'framer-motion';
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

function buildStatusItems(
  role: string,
  workspace: string
): SettingsStatusItem[] {
  const roleHints: Record<string, string> = {
    admin: 'Full governance access',
    user: 'Standard workspace access',
    viewer: 'Read-only access',
  };

  return [
    {
      label: 'Workspace',
      value: workspace,
      hint: 'Active tenant context',
      icon: BriefcaseBusiness,
    },
    {
      label: 'Role',
      value: role.charAt(0).toUpperCase() + role.slice(1),
      hint: roleHints[role] ?? 'Workspace member',
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
      label: 'API access',
      value: '2 tokens',
      hint: 'OpenAI and Anthropic ready',
      icon: KeyRound,
    },
  ];
}

// Single warm-gold Sol accent across every area card — no second accent.
const CARD_ACCENT = 'bg-primary/10 text-primary';

const SETTINGS_CARDS: SettingsCardItem[] = [
  {
    title: 'Profile and preferences',
    description: 'Identity, timezone, display defaults, and notification tone.',
    summary:
      'Primary email, profile defaults, and personal workspace behavior.',
    href: '#personal-preferences',
    cta: 'Jump to personal controls',
    icon: UserCircle2,
    accent: CARD_ACCENT,
  },
  {
    title: 'Workspace and access',
    description: 'Tenant identity, members, roles, and collaboration controls.',
    summary: 'Manage workspace context, membership, and administrative access.',
    href: '/settings/organization',
    cta: 'Open workspace and access',
    icon: BriefcaseBusiness,
    accent: CARD_ACCENT,
  },
  {
    title: 'Security and compliance',
    description:
      'Authentication posture, audit controls, and policy readiness.',
    summary:
      'Review session protection, audit posture, and governance controls.',
    href: '/settings/organization',
    cta: 'Open security and compliance',
    icon: ShieldCheck,
    accent: CARD_ACCENT,
  },
  {
    title: 'Usage and billing',
    description: 'Plan tier, compute consumption, storage, and renewal timing.',
    summary: 'Track credits, document capacity, and billing visibility.',
    href: '/settings/organization',
    cta: 'Open usage and billing',
    icon: CreditCard,
    accent: CARD_ACCENT,
  },
  {
    title: 'Developer access',
    description: 'Token inventory, provider readiness, and scope visibility.',
    summary: 'Manage API access, token rotation, and developer credentials.',
    href: '/settings/api-keys',
    cta: 'Open developer access',
    icon: KeyRound,
    accent: CARD_ACCENT,
  },
  {
    title: 'Connected systems',
    description: 'Provider connectivity and external integration readiness.',
    summary: 'See which model and integration surfaces are ready to use.',
    href: '/settings/api-keys',
    cta: 'Open connected systems',
    icon: Workflow,
    accent: CARD_ACCENT,
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

  const STATUS_ITEMS = buildStatusItems(
    user?.role || 'user',
    'Default Workspace'
  );
  const operatorInitial = operatorName.charAt(0).toUpperCase();

  const togglePreference = (key: PreferenceKey, checked: boolean): void => {
    setPreferences((current) => ({
      ...current,
      [key]: checked,
    }));
  };

  return (
    <MotionConfig reducedMotion="user">
      <div className="space-y-8 px-6 pb-20 pt-6 md:space-y-10 md:px-10 md:pb-24 md:pt-8 lg:px-12">
        <motion.header
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="space-y-4"
        >
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <SlidersHorizontal aria-hidden="true" className="h-6 w-6" />
            </div>
            <div className="space-y-1">
              <h1 className="text-xl font-semibold text-foreground">
                Settings
              </h1>
              <p className="max-w-3xl text-sm text-muted-foreground">
                Manage your account, workspace governance, model access, and
                platform controls.
              </p>
            </div>
          </div>

          <Card className="overflow-hidden rounded-xl border-border bg-card shadow-sm">
            <CardContent className="grid gap-4 p-5 sm:p-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
              <div className="flex items-start gap-3">
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-lg font-semibold text-primary">
                  {operatorInitial}
                </div>
                <div className="space-y-2">
                  <div className="space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-lg font-semibold text-foreground">
                        {operatorName}
                      </p>
                      <span className="inline-flex items-center rounded-full border border-border bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
                        Administrator
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {primaryEmail}
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid gap-3 rounded-xl border border-border bg-muted/20 p-3.5 sm:p-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Last sign-in
                    </p>
                    <div className="flex items-center gap-2 text-sm text-foreground">
                      <Clock3
                        aria-hidden="true"
                        className="h-4 w-4 text-muted-foreground"
                      />
                      Today at 09:10
                    </div>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Session trust
                    </p>
                    <div className="flex items-center gap-2 text-sm text-foreground">
                      <BadgeCheck
                        aria-hidden="true"
                        className="h-4 w-4 text-[var(--nous-terra)]"
                      />
                      Verified operator context
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  {TRUST_ITEMS.map((item) => (
                    <span
                      key={item}
                      className="inline-flex items-center rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.header>

        <section className="space-y-3" aria-labelledby="settings-status-title">
          <div className="flex items-center gap-2">
            <Sparkles aria-hidden="true" className="h-4 w-4 text-primary" />
            <h2
              id="settings-status-title"
              className="text-sm font-medium text-foreground"
            >
              Operating status
            </h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {STATUS_ITEMS.map((item) => {
              const Icon = item.icon;

              return (
                <Card
                  key={item.label}
                  className="rounded-xl border-border bg-card shadow-sm"
                >
                  <CardContent className="space-y-2 p-4">
                    <div className="flex items-center gap-2">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted text-primary">
                        <Icon aria-hidden="true" className="h-4 w-4" />
                      </div>
                      <p className="text-xs font-medium text-muted-foreground">
                        {item.label}
                      </p>
                    </div>
                    <p className="text-xl font-semibold leading-tight text-foreground">
                      {item.value}
                    </p>
                    <p className="text-sm text-muted-foreground">{item.hint}</p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </section>

        <section className="space-y-3" aria-labelledby="settings-areas-title">
          <div className="flex items-center gap-2">
            <SlidersHorizontal
              aria-hidden="true"
              className="h-4 w-4 text-primary"
            />
            <h2
              id="settings-areas-title"
              className="text-sm font-medium text-foreground"
            >
              Settings areas
            </h2>
          </div>
          <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
            {SETTINGS_CARDS.map((item) => {
              const Icon = item.icon;
              const actionClassName =
                'inline-flex items-center gap-2 text-sm font-medium text-foreground transition-colors duration-200 group-hover:text-primary';
              const actionContent = (
                <>
                  {item.cta}
                  <ArrowRight
                    aria-hidden="true"
                    className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5"
                  />
                </>
              );

              return (
                <Card
                  key={item.title}
                  className="group rounded-xl border-border bg-card shadow-sm transition-all duration-200 hover:border-[var(--nous-helios)] hover:shadow-md"
                >
                  <CardHeader className="space-y-3 p-5 pb-2">
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-xl ${item.accent}`}
                    >
                      <Icon aria-hidden="true" className="h-5 w-5" />
                    </div>
                    <div className="space-y-2">
                      <CardTitle className="text-lg font-semibold text-foreground">
                        {item.title}
                      </CardTitle>
                      <p className="text-sm leading-6 text-muted-foreground">
                        {item.description}
                      </p>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3 p-5 pt-0">
                    <p className="text-sm leading-6 text-foreground">
                      {item.summary}
                    </p>
                    <div className="border-t border-border pt-2">
                      {item.href.startsWith('#') ? (
                        <a
                          href={item.href}
                          className={`${actionClassName} rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2`}
                        >
                          {actionContent}
                        </a>
                      ) : (
                        <Link
                          href={item.href}
                          className={`${actionClassName} rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2`}
                        >
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
          <Card className="rounded-xl border-border bg-card shadow-sm">
            <CardHeader className="space-y-2 p-5 pb-2">
              <div className="flex items-center gap-2">
                <Bell aria-hidden="true" className="h-4 w-4 text-primary" />
                <p className="text-sm font-medium text-foreground">
                  Personal controls
                </p>
              </div>
              <div className="space-y-2">
                <CardTitle
                  id="personal-preferences-title"
                  className="text-lg font-semibold text-foreground"
                >
                  Personal preferences
                </CardTitle>
                <p className="max-w-3xl text-sm text-muted-foreground">
                  Keep quick personal defaults on the overview page. These
                  controls stay local in this pass and do not write to backend
                  settings yet.
                </p>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 p-5 pt-0">
              {PREFERENCE_ITEMS.map((item, index) => (
                <div key={item.key} className="space-y-4">
                  {index > 0 && <Separator className="bg-border" />}
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="space-y-1">
                      <Label
                        htmlFor={item.key}
                        className="text-sm font-medium text-foreground"
                      >
                        {item.label}
                      </Label>
                      <p className="text-sm text-muted-foreground">
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
    </MotionConfig>
  );
}
