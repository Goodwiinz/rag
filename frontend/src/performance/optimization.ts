/**
 * Frontend performance optimization utilities for the Multimodal Enterprise RAG System
 */

import { useCallback, useMemo, useEffect, useRef, useState } from 'react';
import { debounce, throttle } from 'lodash-es';

// Performance monitoring utilities
export interface PerformanceMetrics {
  name: string;
  startTime: number;
  endTime: number;
  duration: number;
  memoryBefore?: number;
  memoryAfter?: number;
}

export class PerformanceMonitor {
  private static instance: PerformanceMonitor;
  private metrics: PerformanceMetrics[] = [];
  private observers: PerformanceObserver[] = [];

  static getInstance(): PerformanceMonitor {
    if (!PerformanceMonitor.instance) {
      PerformanceMonitor.instance = new PerformanceMonitor();
    }
    return PerformanceMonitor.instance;
  }

  startMeasure(name: string): PerformanceMetrics {
    const memoryBefore = this.getMemoryUsage();
    const startTime = performance.now();

    const metric: PerformanceMetrics = {
      name,
      startTime,
      endTime: 0,
      duration: 0,
      memoryBefore
    };

    this.metrics.push(metric);
    performance.mark(`${name}-start`);
    return metric;
  }

  endMeasure(name: string): PerformanceMetrics | null {
    const metric = this.metrics.find(m => m.name === name && m.endTime === 0);
    if (!metric) return null;

    const endTime = performance.now();
    metric.endTime = endTime;
    metric.duration = endTime - metric.startTime;
    metric.memoryAfter = this.getMemoryUsage();

    performance.mark(`${name}-end`);
    performance.measure(name, `${name}-start`, `${name}-end`);

    return metric;
  }

  getMetrics(): PerformanceMetrics[] {
    return this.metrics.filter(m => m.endTime > 0);
  }

  getAverageMetric(name: string): number | null {
    const nameMetrics = this.getMetrics().filter(m => m.name === name);
    if (nameMetrics.length === 0) return null;

    const total = nameMetrics.reduce((sum, m) => sum + m.duration, 0);
    return total / nameMetrics.length;
  }

  getMemoryUsage(): number {
    return (performance as any).memory?.usedJSHeapSize || 0;
  }

  startLongTaskObserver(): void {
    if ('PerformanceObserver' in window) {
      const observer = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        entries.forEach((entry) => {
          if (entry.duration > 50) { // Long tasks over 50ms
            console.warn(`Long task detected: ${entry.name} took ${entry.duration}ms`);
          }
        });
      });

      observer.observe({ entryTypes: ['longtask'] });
      this.observers.push(observer);
    }
  }

  cleanup(): void {
    this.observers.forEach(observer => observer.disconnect());
    this.observers = [];
    this.metrics = [];
  }
}

// Image optimization utilities
export class ImageOptimizer {
  private static imageCache = new Map<string, string>();
  private static loadingPromises = new Map<string, Promise<string>>();

  static async loadImage(src: string, options: {
    width?: number;
    height?: number;
    quality?: number;
    format?: 'webp' | 'jpeg' | 'png';
  } = {}): Promise<string> {
    const cacheKey = `${src}-${JSON.stringify(options)}`;

    // Return cached image if available
    if (this.imageCache.has(cacheKey)) {
      return this.imageCache.get(cacheKey)!;
    }

    // Return existing promise if image is currently loading
    if (this.loadingPromises.has(cacheKey)) {
      return this.loadingPromises.get(cacheKey)!;
    }

    // Load and optimize image
    const promise = this.optimizeImage(src, options);
    this.loadingPromises.set(cacheKey, promise);

    try {
      const optimizedSrc = await promise;
      this.imageCache.set(cacheKey, optimizedSrc);
      return optimizedSrc;
    } finally {
      this.loadingPromises.delete(cacheKey);
    }
  }

  private static async optimizeImage(
    src: string,
    options: {
      width?: number;
      height?: number;
      quality?: number;
      format?: 'webp' | 'jpeg' | 'png';
    }
  ): Promise<string> {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = 'anonymous';

      img.onload = () => {
        try {
          const canvas = document.createElement('canvas');
          const ctx = canvas.getContext('2d')!;

          // Calculate dimensions
          let width = options.width || img.width;
          let height = options.height || img.height;

          if (options.width && !options.height) {
            height = (img.height * options.width) / img.width;
          } else if (options.height && !options.width) {
            width = (img.width * options.height) / img.height;
          }

          canvas.width = width;
          canvas.height = height;

          // Draw and compress image
          ctx.drawImage(img, 0, 0, width, height);

          // Determine format and quality
          const format = options.format || 'webp';
          const quality = options.quality || 0.8;

          // Convert to blob and create URL
          canvas.toBlob(
            (blob) => {
              if (blob) {
                const url = URL.createObjectURL(blob);
                resolve(url);
              } else {
                reject(new Error('Failed to create blob'));
              }
            },
            `image/${format}`,
            quality
          );
        } catch (error) {
          reject(error);
        }
      };

      img.onerror = () => reject(new Error(`Failed to load image: ${src}`));
      img.src = src;
    });
  }

  static preloadImages(sources: string[]): Promise<void[]> {
    const promises = sources.map(src =>
      this.loadImage(src).catch(error => {
        console.warn(`Failed to preload image: ${src}`, error);
        return src;
      })
    );

    return Promise.all(promises);
  }
}

// Code splitting and lazy loading utilities
export class CodeSplitOptimizer {
  private static loadedModules = new Set<string>();

  static async loadComponent<T>(
    componentLoader: () => Promise<T>,
    moduleName: string
  ): Promise<T> {
    if (this.loadedModules.has(moduleName)) {
      return componentLoader();
    }

    const monitor = PerformanceMonitor.getInstance();
    monitor.startMeasure(`load-module-${moduleName}`);

    try {
      const component = await componentLoader();
      this.loadedModules.add(moduleName);
      return component;
    } finally {
      monitor.endMeasure(`load-module-${moduleName}`);
    }
  }

  static preloadComponent(componentLoader: () => Promise<any>, moduleName: string): void {
    if (!this.loadedModules.has(moduleName)) {
      // Low priority preloading
      requestIdleCallback(() => {
        componentLoader().then(() => {
          this.loadedModules.add(moduleName);
        }).catch(error => {
          console.warn(`Failed to preload module: ${moduleName}`, error);
        });
      });
    }
  }
}

// Bundle optimization utilities
export class BundleOptimizer {
  private static criticalCSSLoaded = false;
  private static fontPromises = new Map<string, Promise<void>>();

  static async loadCriticalCSS(href: string): Promise<void> {
    if (this.criticalCSSLoaded) return;

    return new Promise((resolve, reject) => {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = href;
      link.onload = () => {
        this.criticalCSSLoaded = true;
        resolve();
      };
      link.onerror = reject;
      document.head.appendChild(link);
    });
  }

  static async loadFont(fontUrl: string, fontFamily: string): Promise<void> {
    if (this.fontPromises.has(fontUrl)) {
      return this.fontPromises.get(fontUrl)!;
    }

    const promise = new Promise<void>((resolve, reject) => {
      const font = new FontFace(fontFamily, `url(${fontUrl})`);
      font.load().then(() => {
        (document.fonts as any).add(font);
        resolve();
      }).catch(reject);
    });

    this.fontPromises.set(fontUrl, promise);
    return promise;
  }

  static preloadResources(resources: Array<{
    url: string;
    type: 'script' | 'style' | 'image' | 'font';
    priority?: 'high' | 'low';
  }>): void {
    resources.forEach(resource => {
      const link = document.createElement('link');
      link.rel = 'preload';
      link.href = resource.url;

      switch (resource.type) {
        case 'script':
          link.as = 'script';
          break;
        case 'style':
          link.as = 'style';
          break;
        case 'image':
          link.as = 'image';
          break;
        case 'font':
          link.as = 'font';
          link.type = 'font/woff2';
          link.crossOrigin = 'anonymous';
          break;
      }

      if (resource.priority === 'high') {
        // Add to critical loading path
        document.head.appendChild(link);
      } else {
        // Low priority loading
        requestIdleCallback(() => {
          document.head.appendChild(link);
        });
      }
    });
  }
}

// Network optimization utilities
export class NetworkOptimizer {
  private static requestCache = new Map<string, Promise<any>>();
  private static responseCache = new Map<string, { data: any; timestamp: number; ttl: number }>();

  static async cachedFetch<T>(
    url: string,
    options: RequestInit & { cacheTTL?: number } = {}
  ): Promise<T> {
    const cacheKey = `${url}-${JSON.stringify(options)}`;
    const cacheTTL = options.cacheTTL || 300000; // 5 minutes default

    // Check cache first
    const cached = this.responseCache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < cached.ttl) {
      return cached.data;
    }

    // Return existing promise if request is in flight
    if (this.requestCache.has(cacheKey)) {
      return this.requestCache.get(cacheKey);
    }

    // Make request
    const promise = fetch(url, options).then(async response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      // Cache response
      this.responseCache.set(cacheKey, {
        data,
        timestamp: Date.now(),
        ttl: cacheTTL
      });

      return data;
    }).finally(() => {
      this.requestCache.delete(cacheKey);
    });

    this.requestCache.set(cacheKey, promise);
    return promise;
  }

  static batchRequests<T>(requests: Array<{
    url: string;
    options?: RequestInit;
  }>, batchSize: number = 6): Promise<T[]> {
    const batches: Array<Array<{ url: string; options?: RequestInit }>> = [];

    for (let i = 0; i < requests.length; i += batchSize) {
      batches.push(requests.slice(i, i + batchSize));
    }

    return batches.reduce(async (previousBatch, currentBatch) => {
      const previousResults = await previousBatch;
      const currentResults = await Promise.all(
        currentBatch.map(req => this.cachedFetch(req.url, req.options))
      );
      return [...previousResults, ...currentResults];
    }, Promise.resolve([] as T[]));
  }

  static clearCache(pattern?: string): void {
    if (pattern) {
      const keysToDelete = Array.from(this.responseCache.keys())
        .filter(key => key.includes(pattern));
      keysToDelete.forEach(key => this.responseCache.delete(key));
    } else {
      this.responseCache.clear();
    }
  }
}

// React hooks for performance optimization
export function usePerformanceMonitor(componentName: string) {
  const monitor = useRef(PerformanceMonitor.getInstance());
  const mountTime = useRef<number>();

  useEffect(() => {
    mountTime.current = performance.now();
    monitor.current.startMeasure(`component-${componentName}`);

    return () => {
      if (mountTime.current) {
        const renderTime = performance.now() - mountTime.current;
        if (renderTime > 16.67) { // More than one frame
          console.warn(`Slow render detected: ${componentName} took ${renderTime.toFixed(2)}ms`);
        }
      }
      monitor.current.endMeasure(`component-${componentName}`);
    };
  }, [componentName]);

  const startMeasure = useCallback((name: string) => {
    return monitor.current.startMeasure(`${componentName}-${name}`);
  }, [componentName]);

  const endMeasure = useCallback((name: string) => {
    return monitor.current.endMeasure(`${componentName}-${name}`);
  }, [componentName]);

  return { startMeasure, endMeasure };
}

export function useDebouncedCallback<T extends (...args: any[]) => any>(
  callback: T,
  delay: number,
  deps: React.DependencyList = []
): T {
  const debouncedCallback = useMemo(
    () => debounce(callback, delay),
    deps
  );

  useEffect(() => {
    return () => {
      debouncedCallback.cancel();
    };
  }, [debouncedCallback]);

  return debouncedCallback as T;
}

export function useThrottledCallback<T extends (...args: any[]) => any>(
  callback: T,
  delay: number,
  deps: React.DependencyList = []
): T {
  const throttledCallback = useMemo(
    () => throttle(callback, delay),
    deps
  );

  useEffect(() => {
    return () => {
      throttledCallback.cancel();
    };
  }, [throttledCallback]);

  return throttledCallback as T;
}

export function useVirtualizedList<T>(
  items: T[],
  itemHeight: number,
  containerHeight: number,
  overscan: number = 5
) {
  const [scrollTop, setScrollTop] = useState(0);

  const visibleStart = Math.floor(scrollTop / itemHeight);
  const visibleEnd = Math.min(
    visibleStart + Math.ceil(containerHeight / itemHeight) + overscan,
    items.length - 1
  );

  const visibleItems = useMemo(() => {
    return items.slice(visibleStart, visibleEnd + 1).map((item, index) => ({
      item,
      index: visibleStart + index
    }));
  }, [items, visibleStart, visibleEnd]);

  const totalHeight = items.length * itemHeight;

  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  return {
    visibleItems,
    totalHeight,
    startIndex: visibleStart,
    endIndex: visibleEnd,
    handleScroll
  };
}

export function useLazyLoad(
  threshold: number = 0.1,
  rootMargin: string = '50px'
) {
  const [isVisible, setIsVisible] = useState(false);
  const elementRef = useRef<HTMLElement>();

  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { threshold, rootMargin }
    );

    observer.observe(element);

    return () => observer.disconnect();
  }, [threshold, rootMargin]);

  return { isVisible, elementRef };
}

// Performance optimization utilities
export function optimizeImagesOnLoad(): void {
  const images = document.querySelectorAll('img[data-src]');

  const imageObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target as HTMLImageElement;
        const src = img.dataset.src;

        if (src) {
          ImageOptimizer.loadImage(src, {
            width: img.width || undefined,
            height: img.height || undefined,
            quality: 0.8,
            format: 'webp'
          }).then(optimizedSrc => {
            img.src = optimizedSrc;
            img.removeAttribute('data-src');
          }).catch(error => {
            console.warn('Failed to load optimized image:', error);
            img.src = src; // Fallback to original
          });
        }

        imageObserver.unobserve(img);
      }
    });
  }, {
    rootMargin: '50px'
  });

  images.forEach(img => imageObserver.observe(img));
}

export function preloadCriticalResources(): void {
  // Preload critical CSS
  BundleOptimizer.loadCriticalCSS('/css/critical.css');

  // Preload critical fonts
  BundleOptimizer.loadFont('/fonts/inter-var.woff2', 'Inter var');

  // Preload critical images
  const criticalImages = [
    '/images/hero-bg.webp',
    '/images/logo.webp'
  ];

  ImageOptimizer.preloadImages(criticalImages);

  // Preload critical JavaScript chunks
  BundleOptimizer.preloadResources([
    { url: '/js/vendor~main.js', type: 'script', priority: 'high' },
    { url: '/js/main.js', type: 'script', priority: 'high' }
  ]);
}

// Initialize performance monitoring
export function initializePerformanceOptimization(): void {
  const monitor = PerformanceMonitor.getInstance();

  // Start long task monitoring
  monitor.startLongTaskObserver();

  // Preload critical resources
  if (typeof requestIdleCallback !== 'undefined') {
    requestIdleCallback(() => {
      preloadCriticalResources();
    });
  } else {
    setTimeout(preloadCriticalResources, 100);
  }

  // Optimize images on page load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', optimizeImagesOnLoad);
  } else {
    optimizeImagesOnLoad();
  }

  // Monitor Core Web Vitals
  if ('web-vitals' in window) {
    import('web-vitals').then(({ getCLS, getFID, getFCP, getLCP, getTTFB }) => {
      getCLS(console.log);
      getFID(console.log);
      getFCP(console.log);
      getLCP(console.log);
      getTTFB(console.log);
    });
  }
}

export default {
  PerformanceMonitor,
  ImageOptimizer,
  CodeSplitOptimizer,
  BundleOptimizer,
  NetworkOptimizer,
  usePerformanceMonitor,
  useDebouncedCallback,
  useThrottledCallback,
  useVirtualizedList,
  useLazyLoad,
  optimizeImagesOnLoad,
  preloadCriticalResources,
  initializePerformanceOptimization
};