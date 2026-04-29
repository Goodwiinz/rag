'use client';

import { useAuth } from '@/hooks';
import {
  LogLevel,
  StatsigProvider,
  useClientAsyncInit,
} from '@statsig/react-bindings';
import { StatsigSessionReplayPlugin } from '@statsig/session-replay';
import { StatsigAutoCapturePlugin } from '@statsig/web-analytics';
import { useEffect, useMemo } from 'react';

interface StatsigClientProviderProps {
  children: React.ReactNode;
}

const SDK_KEY = process.env.NEXT_PUBLIC_STATSIG_CLIENT_KEY;

export function StatsigClientProvider({ children }: StatsigClientProviderProps) {
  const { user } = useAuth();

  const statsigUser = useMemo(
    () => ({
      userID: user?.id ?? 'anonymous',
      email: user?.email,
      customIDs: user?.organization_id
        ? { organizationID: user.organization_id }
        : undefined,
      custom: user
        ? { role: user.role, organization_id: user.organization_id }
        : undefined,
    }),
    [user],
  );

  const { client } = useClientAsyncInit(SDK_KEY ?? '', statsigUser, {
    logLevel:
      process.env.NODE_ENV === 'production' ? LogLevel.Warn : LogLevel.Debug,
    plugins: [
      new StatsigSessionReplayPlugin(),
      new StatsigAutoCapturePlugin(),
    ],
  });

  useEffect(() => {
    if (!client) return;
    void client.updateUserAsync(statsigUser);
  }, [client, statsigUser]);

  if (!SDK_KEY) {
    return <>{children}</>;
  }

  return <StatsigProvider client={client}>{children}</StatsigProvider>;
}

export default StatsigClientProvider;
