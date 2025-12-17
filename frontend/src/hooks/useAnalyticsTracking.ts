'use client';

import { useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { getAnalytics } from '@/lib/analytics';

export function useAnalyticsTracking() {
  const router = useRouter();
  const analyticsRef = useRef(getAnalytics());
  const lastPathRef = useRef<string>('');

  // Track page views on route changes
  useEffect(() => {
    const handleRouteChange = () => {
      const currentPath = window.location.pathname;
      if (currentPath !== lastPathRef.current) {
        lastPathRef.current = currentPath;
        analyticsRef.current.trackPageView(
          currentPath,
          document.title
        );
      }
    };

    // Initial page view
    handleRouteChange();

    // Listen for route changes
    const originalPush = router.push;
    const originalReplace = router.replace;
    const originalBack = router.back;

    router.push = (...args) => {
      const result = originalPush(...args);
      setTimeout(handleRouteChange, 0);
      return result;
    };

    router.replace = (...args) => {
      const result = originalReplace(...args);
      setTimeout(handleRouteChange, 0);
      return result;
    };

    router.back = () => {
      originalBack();
      setTimeout(handleRouteChange, 100);
    };

    return () => {
      router.push = originalPush;
      router.replace = originalReplace;
      router.back = originalBack;
    };
  }, [router]);

  // Memoized tracking functions
  const trackEvent = useCallback((
    category: string,
    action: string,
    label?: string,
    value?: number,
    properties?: Record<string, any>
  ) => {
    analyticsRef.current.trackEvent(category, action, label, value, properties);
  }, []);

  const trackDocumentUpload = useCallback((
    fileType: string,
    fileSize: number,
    success: boolean
  ) => {
    analyticsRef.current.trackDocumentUpload(fileType, fileSize, success);
  }, []);

  const trackSearch = useCallback((
    query: string,
    resultsCount: number,
    searchType: 'semantic' | 'keyword' | 'hybrid'
  ) => {
    analyticsRef.current.trackSearch(query, resultsCount, searchType);
  }, []);

  const trackChatMessage = useCallback((
    messageType: 'user' | 'assistant',
    chatType: 'llm' | 'tambo',
    tokens?: number
  ) => {
    analyticsRef.current.trackChatMessage(messageType, chatType, tokens);
  }, []);

  const trackFeatureUsage = useCallback((
    feature: string,
    action: string,
    properties?: Record<string, any>
  ) => {
    analyticsRef.current.trackFeatureUsage(feature, action, properties);
  }, []);

  const trackError = useCallback((
    error: Error,
    context?: string
  ) => {
    analyticsRef.current.trackError(error, context);
  }, []);

  const trackUserInteraction = useCallback((
    element: string,
    action: string,
    properties?: Record<string, any>
  ) => {
    analyticsRef.current.trackUserInteraction(element, action, properties);
  }, []);

  return {
    trackEvent,
    trackDocumentUpload,
    trackSearch,
    trackChatMessage,
    trackFeatureUsage,
    trackError,
    trackUserInteraction,
  };
}

// Convenience hook for tracking specific features
export function useDocumentAnalytics() {
  const { trackDocumentUpload, trackFeatureUsage, trackError } = useAnalyticsTracking();

  return {
    trackUpload: (fileType: string, fileSize: number, success: boolean) => {
      trackDocumentUpload(fileType, fileSize, success);
    },
    trackProcessingStart: (documentId: string) => {
      trackFeatureUsage('document', 'processing_start', { documentId });
    },
    trackProcessingComplete: (documentId: string, duration: number) => {
      trackFeatureUsage('document', 'processing_complete', { documentId, duration });
    },
    trackProcessingError: (documentId: string, error: Error) => {
      trackError(error, `document_processing_${documentId}`);
    },
    trackDownload: (documentId: string, format: string) => {
      trackFeatureUsage('document', 'download', { documentId, format });
    },
    trackShare: (documentId: string, method: string) => {
      trackFeatureUsage('document', 'share', { documentId, method });
    },
  };
}

export function useSearchAnalytics() {
  const { trackSearch, trackFeatureUsage, trackUserInteraction } = useAnalyticsTracking();

  return {
    trackSearchPerformed: (query: string, resultsCount: number, searchType: 'semantic' | 'keyword' | 'hybrid') => {
      trackSearch(query, resultsCount, searchType);
    },
    trackFilterApplied: (filterType: string, value: string) => {
      trackFeatureUsage('search', 'filter_applied', { filterType, value });
    },
    trackResultClick: (resultId: string, position: number, query: string) => {
      trackUserInteraction('search_result', 'click', { resultId, position, query });
    },
    trackNoResults: (query: string, suggestions?: string[]) => {
      trackFeatureUsage('search', 'no_results', { query, suggestions });
    },
    trackSearchRefinement: (originalQuery: string, refinedQuery: string) => {
      trackFeatureUsage('search', 'refinement', { originalQuery, refinedQuery });
    },
  };
}

export function useChatAnalytics() {
  const { trackChatMessage, trackFeatureUsage, trackUserInteraction } = useAnalyticsTracking();

  return {
    trackMessageSent: (messageType: 'user' | 'assistant', chatType: 'llm' | 'tambo', tokens?: number) => {
      trackChatMessage(messageType, chatType, tokens);
    },
    trackSessionStart: (chatType: 'llm' | 'tambo') => {
      trackFeatureUsage('chat', 'session_start', { chatType });
    },
    trackSessionEnd: (chatType: 'llm' | 'tambo', duration: number, messageCount: number) => {
      trackFeatureUsage('chat', 'session_end', { chatType, duration, messageCount });
    },
    trackFeedback: (messageId: string, rating: number, comment?: string) => {
      trackUserInteraction('chat_message', 'feedback', { messageId, rating, comment });
    },
    trackCopyMessage: (messageType: 'user' | 'assistant') => {
      trackUserInteraction('chat_message', 'copy', { messageType });
    },
    trackRegenerateResponse: (messageId: string) => {
      trackUserInteraction('chat_message', 'regenerate', { messageId });
    },
  };
}

export function useUIAnalytics() {
  const { trackUserInteraction, trackFeatureUsage } = useAnalyticsTracking();

  return {
    trackClick: (element: string, properties?: Record<string, any>) => {
      trackUserInteraction(element, 'click', properties);
    },
    trackHover: (element: string, duration?: number) => {
      trackUserInteraction(element, 'hover', { duration });
    },
    trackScroll: (element: string, depth: number) => {
      trackUserInteraction(element, 'scroll', { depth });
    },
    trackFormSubmit: (formName: string, success: boolean, errors?: string[]) => {
      trackUserInteraction(formName, 'submit', { success, errors });
    },
    trackModalOpen: (modalName: string, trigger?: string) => {
      trackFeatureUsage('ui', 'modal_open', { modalName, trigger });
    },
    trackModalClose: (modalName: string, duration?: number) => {
      trackFeatureUsage('ui', 'modal_close', { modalName, duration });
    },
    trackNavigation: (from: string, to: string, method?: string) => {
      trackUserInteraction('navigation', 'change', { from, to, method });
    },
    trackFeatureDiscovery: (feature: string, method: string) => {
      trackFeatureUsage('discovery', feature, { method });
    },
  };
}

export default useAnalyticsTracking;