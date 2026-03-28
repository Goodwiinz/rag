'use client';

import { useMemo, useState } from 'react';
import {
  CircleUserRound,
  ChevronRight,
  Link2,
  Plug,
  WalletCards,
  X,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';

type SettingsSection = 'account' | 'usage' | 'apps';
type UsageHistoryView = 'usage' | 'addons';

const sectionItems: Array<{
  id: SettingsSection;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}> = [
  { id: 'account', label: 'OPERATOR_PROFILE', icon: CircleUserRound },
  { id: 'usage', label: 'COMPUTE_USAGE', icon: WalletCards },
  { id: 'apps', label: 'LINKED_SYSTEMS', icon: Link2 },
];

function SectionNavButton({
  label,
  active,
  onClick,
  Icon,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  Icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-base transition-colors',
        active
          ? 'bg-[var(--terminal-surface)] text-[var(--terminal-text)] ring-1 ring-[var(--terminal-border-glow)]'
          : 'text-[var(--terminal-text-dim)] hover:bg-[var(--terminal-surface)] hover:text-[var(--terminal-text)]'
      )}
    >
      <Icon className="h-4 w-4" />
      <span>{label}</span>
    </button>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [activeSection, setActiveSection] =
    useState<SettingsSection>('account');
  const [historyView, setHistoryView] = useState<UsageHistoryView>('usage');

  const primaryEmail = useMemo(
    () => user?.email ?? 'Not provided',
    [user?.email]
  );

  return (
    <div
      data-testid="settings-shell"
      className="flex min-h-screen items-center justify-center bg-[var(--terminal-bg)] p-4 sm:p-8"
    >
      <div
        data-testid="settings-panel"
        className="relative mx-auto w-full max-w-6xl min-h-[700px] overflow-hidden rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-panel)] shadow-[0_20px_80px_rgba(0,0,0,0.55)]"
      >
        <button
          type="button"
          aria-label="Close settings"
          onClick={() => router.back()}
          className="absolute right-4 top-4 z-10 rounded-md p-1.5 text-[var(--terminal-text-dim)] transition-colors hover:bg-[var(--terminal-surface)] hover:text-[var(--terminal-text)]"
        >
          <X className="h-4 w-4" />
        </button>
        <div className="grid grid-cols-1 md:grid-cols-[240px_1fr]">
          <aside className="border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)] p-4 md:border-b-0 md:border-r md:p-5">
            <div className="mb-4 pr-10">
              <h1 className="text-lg font-mono font-semibold text-[var(--terminal-text)] tracking-wider uppercase">
                SYSTEM_CONFIG
              </h1>
            </div>
            <nav className="space-y-1" aria-label="Settings sections">
              {sectionItems.map((section) => (
                <SectionNavButton
                  key={section.id}
                  label={section.label}
                  Icon={section.icon}
                  active={activeSection === section.id}
                  onClick={() => setActiveSection(section.id)}
                />
              ))}
            </nav>
          </aside>

          <main className="min-h-[620px] bg-[var(--terminal-panel)] p-6 sm:p-8">
            {activeSection === 'account' && (
              <section aria-labelledby="my-account-title" className="space-y-6">
                <div>
                  <h2
                    id="my-account-title"
                    className="text-sm font-mono font-semibold text-[var(--phosphor-green)] tracking-wider uppercase"
                  >
                    PRIMARY_IDENTITY
                  </h2>
                  <p className="mt-2 text-xl text-[var(--terminal-text-dim)]">
                    {primaryEmail}
                  </p>
                </div>

                <hr className="border-[var(--terminal-border)]" />

                <div>
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <h3 className="text-sm font-mono font-semibold text-[var(--phosphor-green)] tracking-wider uppercase">
                      ACCESS_TIER
                    </h3>
                    <button
                      type="button"
                      className="inline-flex items-center gap-2 rounded-md border border-[var(--terminal-border-glow)] px-4 py-2 text-base font-medium text-[var(--terminal-text)] hover:bg-[var(--terminal-surface)]"
                    >
                      View Plans
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>
                  <p className="max-w-2xl text-sm font-mono text-[var(--terminal-text-dim)]">
                    Current tier: BASIC_OPERATOR. Upgrade to unlock unlimited
                    neural queries, priority compute, and advanced research
                    workflows.
                  </p>
                </div>

                <hr className="border-[var(--terminal-border)]" />

                <button
                  type="button"
                  className="rounded-md border border-rose-400/60 px-4 py-2 text-base font-medium text-rose-400 hover:bg-rose-500/10"
                >
                  Log out
                </button>
              </section>
            )}

            {activeSection === 'usage' && (
              <section
                aria-labelledby="agent-usage-title"
                className="space-y-7"
              >
                <div className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
                  <div className="rounded-t-xl bg-[var(--terminal-surface)] p-4">
                    <div className="mb-1 flex items-center justify-between gap-3 text-[var(--terminal-text-dim)]">
                      <span className="text-lg">Plan</span>
                      <button
                        type="button"
                        className="rounded-md bg-orange-500 px-4 py-2 text-sm font-semibold text-white hover:bg-orange-600"
                      >
                        Upgrade Plan
                      </button>
                    </div>
                    <p className="text-3xl font-semibold text-[var(--terminal-text)]">
                      Basic
                    </p>
                  </div>

                  <div className="space-y-3 border-t border-[var(--terminal-border)] p-4">
                    <div className="flex items-center justify-between gap-2 text-[var(--terminal-text)]">
                      <span className="text-3xl font-semibold">
                        Monthly Credits
                      </span>
                      <span className="text-3xl font-semibold">100 left</span>
                    </div>
                    <div className="flex items-center justify-between gap-2 text-lg text-[var(--terminal-text-dim)]">
                      <span>Resets March 17, 2026</span>
                      <span>100% left</span>
                    </div>
                  </div>
                </div>

                <div>
                  <h2
                    id="agent-usage-title"
                    className="mb-4 text-3xl font-semibold text-[var(--terminal-text)]"
                  >
                    History
                  </h2>

                  <div className="mb-4 inline-flex rounded-lg bg-[var(--terminal-surface)] p-1">
                    <button
                      type="button"
                      onClick={() => setHistoryView('usage')}
                      className={cn(
                        'rounded-md px-4 py-2 text-base font-medium',
                        historyView === 'usage'
                          ? 'bg-[var(--terminal-panel)] text-[var(--terminal-text)] shadow-sm'
                          : 'text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)]'
                      )}
                    >
                      Usage
                    </button>
                    <button
                      type="button"
                      onClick={() => setHistoryView('addons')}
                      className={cn(
                        'rounded-md px-4 py-2 text-base font-medium',
                        historyView === 'addons'
                          ? 'bg-[var(--terminal-panel)] text-[var(--terminal-text)] shadow-sm'
                          : 'text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)]'
                      )}
                    >
                      Add-On Purchases
                    </button>
                  </div>

                  <div className="overflow-hidden rounded-xl border border-[var(--terminal-border)]">
                    <div className="grid grid-cols-3 border-b border-[var(--terminal-border)] bg-[var(--terminal-surface)] px-4 py-3 text-base font-medium text-[var(--terminal-text-dim)]">
                      <span>Details</span>
                      <span className="text-center">Date</span>
                      <span className="text-right">Credits</span>
                    </div>
                    <div className="px-4 py-8 text-center text-sm font-mono text-[var(--terminal-text-dim)]">
                      NO_COMPUTE_HISTORY
                    </div>
                  </div>
                </div>
              </section>
            )}

            {activeSection === 'apps' && (
              <section
                aria-labelledby="connected-apps-title"
                className="space-y-5"
              >
                <div>
                  <h2
                    id="connected-apps-title"
                    className="text-3xl font-semibold text-[var(--terminal-text)]"
                  >
                    LINKED_SYSTEMS
                  </h2>
                  <p className="mt-2 text-sm font-mono text-[var(--terminal-text-dim)]">
                    Connect external data sources and integrations to extend
                    your neural pipeline.
                  </p>
                </div>

                <div className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)] p-6">
                  <div className="mb-4 flex items-center gap-2 text-[var(--terminal-text)]">
                    <Plug className="h-5 w-5" />
                    <span className="text-sm font-mono font-medium">
                      NO_LINKED_SYSTEMS
                    </span>
                  </div>
                  <p className="mb-4 text-lg text-[var(--terminal-text-dim)]">
                    You can connect apps like Google Drive, Notion, and Slack
                    from here.
                  </p>
                  <button
                    type="button"
                    className="rounded-md border border-[var(--terminal-border-glow)] bg-[var(--terminal-panel)] px-4 py-2 text-base font-medium text-[var(--terminal-text)] hover:bg-[var(--terminal-surface)]"
                  >
                    Connect App
                  </button>
                </div>
              </section>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
