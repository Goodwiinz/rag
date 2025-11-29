import { useEffect, useRef, useCallback, useState } from 'react';

// Performance monitoring utilities
export const performance = {
  // Mark performance milestones
  mark: (name: string) => {
    if (window.performance && window.performance.mark) {
      window.performance.mark(name);
    }
  },

  // Measure time between marks
  measure: (name: string, startMark: string, endMark?: string) => {
    if (window.performance && window.performance.measure) {
      window.performance.measure(name, startMark, endMark);
      const entries = window.performance.getEntriesByName(name);
      return entries.length > 0 ? entries[entries.length - 1]?.duration ?? 0 : 0;
    }
    return 0;
  },

  // Get navigation timing
  getNavigationTiming: () => {
    if (window.performance && window.performance.timing) {
      const timing = window.performance.timing;
      return {
        domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
        loadComplete: timing.loadEventEnd - timing.navigationStart,
        firstPaint: timing.responseStart - timing.navigationStart,
        domInteractive: timing.domInteractive - timing.navigationStart,
      };
    }
    return null;
  },

  // Get resource timing
  getResourceTiming: () => {
    if (window.performance && window.performance.getEntriesByType) {
      return window.performance.getEntriesByType('resource').map((entry) => {
        const resourceEntry = entry as PerformanceResourceTiming;
        return {
          name: entry.name,
          duration: entry.duration,
          size: resourceEntry.transferSize || 0,
          type: resourceEntry.initiatorType || 'other',
        };
      });
    }
    return [];
  },
};

// Performance monitoring hook
export const usePerformanceMonitor = (componentName: string) => {
  const renderStartTime = useRef<number>();

  useEffect(() => {
    renderStartTime.current = window.performance.now();
    performance.mark(`${componentName}-render-start`);

    return () => {
      if (renderStartTime.current) {
        const renderTime = window.performance.now() - renderStartTime.current;
        performance.mark(`${componentName}-render-end`);
        const duration = performance.measure(
          `${componentName}-render-duration`,
          `${componentName}-render-start`,
          `${componentName}-render-end`
        );

        // Log render times in development
        if (process.env.NODE_ENV === 'development') {
          console.log(`${componentName} render time:`, duration.toFixed(2), 'ms');
        }

        // Send to analytics if needed
        if (duration > 16) { // More than one frame
          trackSlowRender(componentName, duration);
        }
      }
    };
  }, [componentName]);
};

// Track slow renders
const trackSlowRender = (componentName: string, duration: number) => {
  // Send to analytics service
  if ((window as any).gtag) {
    (window as any).gtag('event', 'slow_render', {
      component_name: componentName,
      duration: Math.round(duration),
    });
  }
};

// Intersection Observer for lazy loading
export const useIntersectionObserver = (
  ref: React.RefObject<Element>,
  callback: (entry: IntersectionObserverEntry) => void,
  options: IntersectionObserverInit = {}
) => {
  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(([entry]) => {
      if (entry) callback(entry);
    }, {
      threshold: 0.1,
      rootMargin: '50px',
      ...options,
    });

    observer.observe(element);

    return () => {
      observer.unobserve(element);
    };
  }, [ref, callback, options]);
};

// Virtual scrolling hook for large lists
export const useVirtualScroll = <T,>(
  items: T[],
  itemHeight: number,
  containerHeight: number
) => {
  const [scrollTop, setScrollTop] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const startIndex = Math.floor(scrollTop / itemHeight);
  const endIndex = Math.min(
    startIndex + Math.ceil(containerHeight / itemHeight) + 1,
    items.length - 1
  );

  const visibleItems = items.slice(startIndex, endIndex + 1);
  const offsetY = startIndex * itemHeight;

  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  return {
    containerRef,
    visibleItems,
    offsetY,
    totalHeight: items.length * itemHeight,
    handleScroll,
  };
};

// Image lazy loading hook
export const useLazyImage = (src: string, placeholder?: string) => {
  const [imageSrc, setImageSrc] = useState(placeholder || '');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry && entry.isIntersecting) {
          setIsLoading(true);
          setError(false);

          const newImg = new Image();
          newImg.src = src;

          newImg.onload = () => {
            setImageSrc(src);
            setIsLoading(false);
          };

          newImg.onerror = () => {
            setError(true);
            setIsLoading(false);
          };

          observer.unobserve(img);
        }
      },
      { rootMargin: '50px' }
    );

    observer.observe(img);

    return () => observer.disconnect();
  }, [src]);

  return { imageSrc, isLoading, error, imgRef };
};

// Debounce hook for search and filters
export const useDebounce = <T,>(value: T, delay: number): T => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
};

// Throttle hook for scroll events
export const useThrottle = <T extends (...args: any[]) => any>(
  callback: T,
  delay: number
): T => {
  const lastRun = useRef(Date.now());

  return useCallback(
    (...args: Parameters<T>) => {
      if (Date.now() - lastRun.current >= delay) {
        callback(...args);
        lastRun.current = Date.now();
      }
    },
    [callback, delay]
  ) as T;
};

// Memoization utilities
export const memoizeWithWeakMap = <T extends (...args: any[]) => any>(fn: T): T => {
  const cache = new WeakMap();

  return ((...args: any[]) => {
    const key = args[0]; // Simple memoization based on first argument

    if (cache.has(key)) {
      return cache.get(key);
    }

    const result = fn(...args);
    cache.set(key, result);
    return result;
  }) as T;
};

// Bundle size monitoring
export const monitorBundleSize = (): (() => void) | void => {
  if (process.env.NODE_ENV === 'development') {
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const resourceEntry = entry as PerformanceResourceTiming;
        if (entry.name.includes('chunk')) {
          console.log(`Chunk loaded: ${entry.name}, Size: ${resourceEntry.transferSize || 0} bytes`);
        }
      }
    });

    observer.observe({ entryTypes: ['resource'] });

    return () => observer.disconnect();
  }
};

// Core Web Vitals monitoring
export const monitorCoreWebVitals = () => {
  // Largest Contentful Paint (LCP)
  const observeLCP = () => {
    const observer = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const lastEntry = entries[entries.length - 1];
      if (!lastEntry) return;

      const lcpEntry = lastEntry as any;
      console.log('LCP:', lcpEntry.renderTime || lcpEntry.loadTime);

      // Send to analytics
      if ((window as any).gtag) {
        (window as any).gtag('event', 'LCP', {
          value: lcpEntry.renderTime || lcpEntry.loadTime,
        });
      }
    });

    observer.observe({ entryTypes: ['largest-contentful-paint'] });
  };

  // First Input Delay (FID)
  const observeFID = () => {
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const fidEntry = entry as any;
        console.log('FID:', fidEntry.processingStart - entry.startTime);

        // Send to analytics
        if ((window as any).gtag) {
          (window as any).gtag('event', 'FID', {
            value: fidEntry.processingStart - entry.startTime,
          });
        }
      }
    });

    observer.observe({ entryTypes: ['first-input'] });
  };

  // Cumulative Layout Shift (CLS)
  const observeCLS = () => {
    let clsValue = 0;
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!(entry as any).hadRecentInput) {
          clsValue += (entry as any).value;
        }
      }
      console.log('CLS:', clsValue);

      // Send to analytics
      if ((window as any).gtag) {
        (window as any).gtag('event', 'CLS', {
          value: clsValue,
        });
      }
    });

    observer.observe({ entryTypes: ['layout-shift'] });
  };

  // Start observing
  observeLCP();
  observeFID();
  observeCLS();
};

// Service Worker registration for caching
export const registerServiceWorker = async () => {
  if ('serviceWorker' in navigator) {
    try {
      const registration = await navigator.serviceWorker.register('/sw.js');
      console.log('Service Worker registered:', registration);

      // Check for updates
      registration.addEventListener('updatefound', () => {
        const newWorker = registration.installing;
        if (newWorker) {
          newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              // New content available
              if (window.confirm('New content available. Reload page?')) {
                window.location.reload();
              }
            }
          });
        }
      });

      return registration;
    } catch (error) {
      console.error('Service Worker registration failed:', error);
    }
  }
  return null;
};

// Memory usage monitoring (in development)
export const monitorMemoryUsage = () => {
  if (process.env.NODE_ENV === 'development' && 'memory' in performance) {
    const checkMemory = () => {
      const memory = (performance as any).memory;
      console.log('Memory usage:', {
        used: Math.round(memory.usedJSHeapSize / 1048576) + ' MB',
        total: Math.round(memory.totalJSHeapSize / 1048576) + ' MB',
        limit: Math.round(memory.jsHeapSizeLimit / 1048576) + ' MB',
      });
    };

    // Check every 30 seconds
    const interval = setInterval(checkMemory, 30000);

    return () => clearInterval(interval);
  }
  return () => { };
};

// Preload critical resources
export const preloadResource = (href: string, as: string) => {
  const link = document.createElement('link');
  link.rel = 'preload';
  link.href = href;
  link.as = as;
  document.head.appendChild(link);
};

// Prefetch next page resources
export const prefetchPage = (path: string) => {
  const link = document.createElement('link');
  link.rel = 'prefetch';
  link.href = path;
  document.head.appendChild(link);
};

// Optimize images with WebP support
export const getOptimizedImageUrl = (
  baseUrl: string,
  width: number,
  height: number,
  format: 'webp' | 'jpeg' | 'png' = 'webp'
) => {
  const url = new URL(baseUrl, window.location.origin);
  url.searchParams.set('w', width.toString());
  url.searchParams.set('h', height.toString());
  url.searchParams.set('format', format);
  url.searchParams.set('quality', '80');
  return url.toString();
};

// Request animation frame for smooth animations
export const useAnimationFrame = (callback: () => void, deps: any[] = []) => {
  const requestRef = useRef<number>();

  useEffect(() => {
    const animate = () => {
      callback();
      requestRef.current = requestAnimationFrame(animate);
    };

    requestRef.current = requestAnimationFrame(animate);

    return () => {
      if (requestRef.current) {
        cancelAnimationFrame(requestRef.current);
      }
    };
  }, [callback, ...deps]);
};

// Performance metrics collector
export const collectPerformanceMetrics = () => {
  const metrics = {
    navigation: performance.getNavigationTiming(),
    resources: performance.getResourceTiming(),
    memory: (performance as any).memory ? {
      used: (performance as any).memory.usedJSHeapSize,
      total: (performance as any).memory.totalJSHeapSize,
      limit: (performance as any).memory.jsHeapSizeLimit,
    } : null,
  };

  return metrics;
};