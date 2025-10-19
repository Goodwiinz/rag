import React, { createContext, useContext, useEffect, useState } from 'react';

interface AccessibilityContextType {
  // Screen reader support
  announceToScreenReader: (message: string) => void;
  isScreenReaderActive: boolean;

  // Keyboard navigation
  keyboardNavigation: {
    enabled: boolean;
    focusVisible: boolean;
    skipLinks: SkipLink[];
  };

  // Visual accessibility
  highContrastMode: boolean;
  reducedMotion: boolean;
  fontSize: 'small' | 'medium' | 'large';
  lineHeight: 'normal' | 'relaxed' | 'loose';

  // Color blindness support
  colorBlindMode: 'none' | 'protanopia' | 'deuteranopia' | 'tritanopia';

  // Focus management
  focusTrap: (element: HTMLElement) => () => void;
  restoreFocus: () => void;

  // Actions
  setHighContrastMode: (enabled: boolean) => void;
  setReducedMotion: (enabled: boolean) => void;
  setFontSize: (size: 'small' | 'medium' | 'large') => void;
  setLineHeight: (height: 'normal' | 'relaxed' | 'loose') => void;
  setColorBlindMode: (mode: 'none' | 'protanopia' | 'deuteranopia' | 'tritanopia') => void;
}

interface SkipLink {
  id: string;
  href: string;
  text: string;
}

const AccessibilityContext = createContext<AccessibilityContextType | null>(null);

export const useAccessibility = () => {
  const context = useContext(AccessibilityContext);
  if (!context) {
    throw new Error('useAccessibility must be used within AccessibilityProvider');
  }
  return context;
};

export const AccessibilityProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isScreenReaderActive, setIsScreenReaderActive] = useState(false);
  const [highContrastMode, setHighContrastMode] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [fontSize, setFontSize] = useState<'small' | 'medium' | 'large'>('medium');
  const [lineHeight, setLineHeight] = useState<'normal' | 'relaxed' | 'loose'>('normal');
  const [colorBlindMode, setColorBlindMode] = useState<'none' | 'protanopia' | 'deuteranopia' | 'tritanopia'>('none');
  const [focusVisible, setFocusVisible] = useState(false);
  const [previousFocusElement, setPreviousFocusElement] = useState<HTMLElement | null>(null);
  const [skipLinks, setSkipLinks] = useState<SkipLink[]>([]);

  // Detect screen reader and accessibility preferences
  useEffect(() => {
    // Check for reduced motion preference
    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(motionQuery.matches);

    // Check for high contrast preference
    const contrastQuery = window.matchMedia('(prefers-contrast: high)');
    setHighContrastMode(contrastQuery.matches);

    // Listen for preference changes
    const handleMotionChange = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    const handleContrastChange = (e: MediaQueryListEvent) => setHighContrastMode(e.matches);

    motionQuery.addEventListener('change', handleMotionChange);
    contrastQuery.addEventListener('change', handleContrastChange);

    // Detect screen reader usage
    const handleScreenReaderDetection = () => {
      // Simple detection based on aria-live region changes
      const testElement = document.createElement('div');
      testElement.setAttribute('aria-live', 'polite');
      testElement.setAttribute('aria-atomic', 'true');
      testElement.style.position = 'absolute';
      testElement.style.left = '-10000px';
      testElement.textContent = 'Screen reader test';
      document.body.appendChild(testElement);

      setTimeout(() => {
        if (testElement.textContent === '') {
          setIsScreenReaderActive(true);
        }
        document.body.removeChild(testElement);
      }, 100);
    };

    handleScreenReaderDetection();

    return () => {
      motionQuery.removeEventListener('change', handleMotionChange);
      contrastQuery.removeEventListener('change', handleContrastChange);
    };
  }, []);

  // Keyboard navigation handling
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Tab navigation
      if (e.key === 'Tab') {
        setFocusVisible(true);
        document.body.setAttribute('data-keyboard-nav', 'true');
      }

      // Escape key
      if (e.key === 'Escape') {
        restoreFocus();
      }

      // Alt + S for skip links
      if (e.altKey && e.key === 's') {
        e.preventDefault();
        const firstSkipLink = document.querySelector('.skip-link');
        if (firstSkipLink) {
          (firstSkipLink as HTMLElement).focus();
        }
      }
    };

    const handleMouseDown = () => {
      setFocusVisible(false);
      document.body.removeAttribute('data-keyboard-nav');
    };

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handleMouseDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleMouseDown);
    };
  }, []);

  // Apply accessibility classes to document
  useEffect(() => {
    const root = document.documentElement;

    // High contrast
    if (highContrastMode) {
      root.classList.add('high-contrast');
    } else {
      root.classList.remove('high-contrast');
    }

    // Reduced motion
    if (reducedMotion) {
      root.classList.add('reduce-motion');
    } else {
      root.classList.remove('reduce-motion');
    }

    // Font size
    root.setAttribute('data-font-size', fontSize);

    // Line height
    root.setAttribute('data-line-height', lineHeight);

    // Color blind mode
    root.setAttribute('data-color-blind', colorBlindMode);
  }, [highContrastMode, reducedMotion, fontSize, lineHeight, colorBlindMode]);

  // Screen reader announcements
  const announceToScreenReader = (message: string) => {
    const announcement = document.createElement('div');
    announcement.setAttribute('aria-live', 'polite');
    announcement.setAttribute('aria-atomic', 'true');
    announcement.className = 'sr-only';
    announcement.textContent = message;

    document.body.appendChild(announcement);

    // Remove after announcement
    setTimeout(() => {
      document.body.removeChild(announcement);
    }, 1000);
  };

  // Focus management
  const focusTrap = (element: HTMLElement) => {
    const focusableElements = element.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    ) as NodeListOf<HTMLElement>;

    const firstFocusable = focusableElements[0];
    const lastFocusable = focusableElements[focusableElements.length - 1];

    // Store current focus
    setPreviousFocusElement(document.activeElement as HTMLElement);

    // Focus first element
    if (firstFocusable) {
      firstFocusable.focus();
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Tab') {
        if (e.shiftKey) {
          // Shift + Tab
          if (document.activeElement === firstFocusable) {
            e.preventDefault();
            lastFocusable?.focus();
          }
        } else {
          // Tab
          if (document.activeElement === lastFocusable) {
            e.preventDefault();
            firstFocusable?.focus();
          }
        }
      }
    };

    element.addEventListener('keydown', handleKeyDown);

    // Return cleanup function
    return () => {
      element.removeEventListener('keydown', handleKeyDown);
      restoreFocus();
    };
  };

  const restoreFocus = () => {
    if (previousFocusElement && previousFocusElement.focus) {
      previousFocusElement.focus();
    }
  };

  // Generate skip links dynamically
  useEffect(() => {
    const mainContent = document.querySelector('main');
    const navigation = document.querySelector('nav');
    const sidebar = document.querySelector('[role="complementary"]');

    const links: SkipLink[] = [];

    if (mainContent) {
      links.push({
        id: 'skip-to-main',
        href: '#main-content',
        text: 'Skip to main content',
      });
    }

    if (navigation) {
      links.push({
        id: 'skip-to-nav',
        href: '#navigation',
        text: 'Skip to navigation',
      });
    }

    if (sidebar) {
      links.push({
        id: 'skip-to-sidebar',
        href: '#sidebar',
        text: 'Skip to sidebar',
      });
    }

    setSkipLinks(links);
  }, []);

  const value: AccessibilityContextType = {
    announceToScreenReader,
    isScreenReaderActive,
    keyboardNavigation: {
      enabled: true,
      focusVisible,
      skipLinks,
    },
    highContrastMode,
    reducedMotion,
    fontSize,
    lineHeight,
    colorBlindMode,
    focusTrap,
    restoreFocus,
    setHighContrastMode,
    setReducedMotion,
    setFontSize,
    setLineHeight,
    setColorBlindMode,
  };

  return (
    <AccessibilityContext.Provider value={value}>
      {/* Skip Links */}
      <div className="skip-links" role="navigation" aria-label="Skip navigation links">
        {skipLinks.map((link) => (
          <a
            key={link.id}
            href={link.href}
            className="skip-link sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 bg-blue-600 text-white px-4 py-2 rounded-md z-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {link.text}
          </a>
        ))}
      </div>

      {/* Screen reader announcements */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        id="screen-reader-announcements"
      />

      {children}
    </AccessibilityContext.Provider>
  );
};

// Custom hook for focus management
export const useFocusManagement = () => {
  const { focusTrap, restoreFocus } = useAccessibility();

  const trapFocus = React.useCallback((element: HTMLElement | null) => {
    if (!element) return () => {};
    return focusTrap(element);
  }, [focusTrap]);

  return { trapFocus, restoreFocus };
};

// Custom hook for keyboard navigation
export const useKeyboardNavigation = () => {
  const { keyboardNavigation } = useAccessibility();

  const handleKeyDown = React.useCallback((e: React.KeyboardEvent, handlers: Record<string, () => void>) => {
    const handler = handlers[e.key];
    if (handler) {
      e.preventDefault();
      handler();
    }
  }, []);

  return {
    focusVisible: keyboardNavigation.focusVisible,
    handleKeyDown,
  };
};

// Custom hook for announcements
export const useAnnouncements = () => {
  const { announceToScreenReader } = useAccessibility();

  const announce = React.useCallback((message: string, priority: 'polite' | 'assertive' = 'polite') => {
    if (priority === 'assertive') {
      // For assertive announcements, we need to use a different approach
      const announcement = document.createElement('div');
      announcement.setAttribute('aria-live', 'assertive');
      announcement.setAttribute('aria-atomic', 'true');
      announcement.className = 'sr-only';
      announcement.textContent = message;

      document.body.appendChild(announcement);

      setTimeout(() => {
        document.body.removeChild(announcement);
      }, 1000);
    } else {
      announceToScreenReader(message);
    }
  }, [announceToScreenReader]);

  return { announce };
};

export default AccessibilityProvider;