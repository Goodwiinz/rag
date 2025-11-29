/**
 * Feature Flags Service for Frontend
 * Integrates with LaunchDarkly React SDK (or mock implementation)
 */

// import { useLDClient } from 'launchdarkly-react-client-sdk';
import React, { useEffect, useState } from 'react';
import { User } from '../types/auth';

export interface FeatureFlagContext {
  key: string;
  email: string;
  name?: string;
  custom?: Record<string, any>;
}

export enum FeatureFlag {
  MULTIMODAL_PROCESSING = 'multimodal-processing',
  ADVANCED_ANALYTICS = 'advanced-analytics',
  EVALUATION_METRICS = 'evaluation-metrics',
  REAL_TIME_PROCESSING = 'real-time-processing',
  EXPERIMENTAL_UI = 'experimental-ui',
  AI_MODEL_OPTIMIZATION = 'ai-model-optimization',
  FILE_UPLOAD_LIMITS = 'file-upload-limits',
  SEARCH_RESULT_COUNT = 'search-result-count',
}

export interface FeatureFlagValues {
  [FeatureFlag.MULTIMODAL_PROCESSING]: boolean;
  [FeatureFlag.ADVANCED_ANALYTICS]: boolean;
  [FeatureFlag.EVALUATION_METRICS]: boolean;
  [FeatureFlag.REAL_TIME_PROCESSING]: boolean;
  [FeatureFlag.EXPERIMENTAL_UI]: boolean;
  [FeatureFlag.AI_MODEL_OPTIMIZATION]: 'standard' | 'optimized' | 'experimental';
  [FeatureFlag.FILE_UPLOAD_LIMITS]: 100 | 500 | 1000;
  [FeatureFlag.SEARCH_RESULT_COUNT]: 10 | 20 | 50;
}

const DEFAULT_FEATURE_FLAGS: FeatureFlagValues = {
  [FeatureFlag.MULTIMODAL_PROCESSING]: false,
  [FeatureFlag.ADVANCED_ANALYTICS]: true,
  [FeatureFlag.EVALUATION_METRICS]: true,
  [FeatureFlag.REAL_TIME_PROCESSING]: false,
  [FeatureFlag.EXPERIMENTAL_UI]: false,
  [FeatureFlag.AI_MODEL_OPTIMIZATION]: 'standard',
  [FeatureFlag.FILE_UPLOAD_LIMITS]: 100,
  [FeatureFlag.SEARCH_RESULT_COUNT]: 10,
};

/**
 * Custom hook for using feature flags
 */
export const useFeatureFlags = (user?: User) => {
  // const ldClient = useLDClient(); // Commented out - LaunchDarkly not installed
  const ldClient = null as any; // Mock client
  const [flags, setFlags] = useState<FeatureFlagValues>(DEFAULT_FEATURE_FLAGS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const initializeFeatureFlags = async () => {
      if (!ldClient || !user) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        // Identify the user in LaunchDarkly
        const context: FeatureFlagContext = {
          key: user.id,
          email: user.email,
          name: user.name,
          custom: {
            role: user.role,
          },
        };

        await ldClient.identify(context);

        // Get all flag values
        const flagValues: Partial<FeatureFlagValues> = {};

        for (const flag of Object.values(FeatureFlag)) {
          flagValues[flag as FeatureFlag] = ldClient.variation(
            flag,
            DEFAULT_FEATURE_FLAGS[flag as FeatureFlag]
          );
        }

        setFlags({ ...DEFAULT_FEATURE_FLAGS, ...flagValues } as FeatureFlagValues);
      } catch (err) {
        console.error('Error initializing feature flags:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    initializeFeatureFlags();
  }, [ldClient, user]);

  const isFeatureEnabled = (flag: FeatureFlag): boolean => {
    if (loading || error) {
      return DEFAULT_FEATURE_FLAGS[flag] as boolean;
    }
    return flags[flag] as boolean;
  };

  const getFeatureValue = <T extends FeatureFlag>(flag: T): FeatureFlagValues[T] => {
    if (loading || error) {
      return DEFAULT_FEATURE_FLAGS[flag];
    }
    return flags[flag];
  };

  const trackFeatureUsage = (feature: FeatureFlag, data?: Record<string, any>) => {
    if (ldClient) {
      ldClient.track(`feature-used`, { feature, ...data });
    }
  };

  return {
    flags,
    loading,
    error,
    isFeatureEnabled,
    getFeatureValue,
    trackFeatureUsage,
  };
};

/**
 * Hook for checking a specific feature flag
 */
export const useFeatureFlag = (flag: FeatureFlag, user?: User) => {
  const { isFeatureEnabled, getFeatureValue, loading, error, trackFeatureUsage } = useFeatureFlags(user);

  const value = getFeatureValue(flag);
  const enabled = isFeatureEnabled(flag);

  const trackUsage = (data?: Record<string, any>) => {
    trackFeatureUsage(flag, data);
  };

  return {
    value,
    enabled,
    loading,
    error,
    trackUsage,
  };
};

/**
 * Feature flag wrapper component for conditional rendering
 */
interface FeatureFlagWrapperProps {
  flag: FeatureFlag;
  children: React.ReactNode;
  fallback?: React.ReactNode;
  user?: User;
  renderWhenEnabled?: boolean;
}

export const FeatureFlagWrapper: React.FC<FeatureFlagWrapperProps> = ({
  flag,
  children,
  fallback = null,
  user,
  renderWhenEnabled = true,
}) => {
  const { enabled, loading } = useFeatureFlag(flag, user);

  if (loading) {
    return null; // or a loading spinner
  }

  const shouldRender = renderWhenEnabled ? enabled : !enabled;

  return shouldRender ? <>{children}</> : <>{fallback}</>;
};

/**
 * Hook for A/B testing
 */
export const useABTest = (testName: string, user?: User) => {
  const { getFeatureValue, loading, error, trackFeatureUsage } = useFeatureFlags(user);

  const variant = getFeatureValue(testName as FeatureFlag);

  const trackConversion = (data?: Record<string, any>) => {
    if (loading || error) return;

    trackFeatureUsage(testName as FeatureFlag, {
      event: 'conversion',
      ...data,
    });
  };

  return {
    variant,
    loading,
    error,
    trackConversion,
  };
};

/**
 * Hook for progressive rollout
 */
export const useProgressiveRollout = (flag: FeatureFlag, user?: User) => {
  const { enabled, loading, error, trackUsage } = useFeatureFlag(flag, user);

  const trackRolloutParticipation = (data?: Record<string, any>) => {
    if (!enabled || loading || error) return;

    trackUsage({
      event: 'rollout-participation',
      ...data,
    });
  };

  return {
    isIncluded: enabled,
    loading,
    error,
    trackRolloutParticipation,
  };
};

/**
 * Service for managing feature flags without React hooks
 */
export class FeatureFlagService {
  private static instance: FeatureFlagService;
  private ldClient: any = null;

  private constructor() {}

  static getInstance(): FeatureFlagService {
    if (!FeatureFlagService.instance) {
      FeatureFlagService.instance = new FeatureFlagService();
    }
    return FeatureFlagService.instance;
  }

  async initialize(user?: User) {
    // This would be initialized in a non-React context
    // Implementation would depend on the LaunchDarkly JS SDK
  }

  isFeatureEnabled(flag: FeatureFlag, defaultValue: boolean = false): boolean {
    // Fallback implementation when React hooks can't be used
    return DEFAULT_FEATURE_FLAGS[flag] as boolean;
  }

  getFeatureValue<T extends FeatureFlag>(flag: T, defaultValue?: FeatureFlagValues[T]): FeatureFlagValues[T] {
    // Fallback implementation
    return defaultValue || DEFAULT_FEATURE_FLAGS[flag];
  }

  trackEvent(eventName: string, data?: Record<string, any>) {
    // Fallback implementation
    console.log('Feature flag event tracked:', eventName, data);
  }
}

// Export default instance
export const featureFlagService = FeatureFlagService.getInstance();