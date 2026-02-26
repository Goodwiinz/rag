/**
 * Type declarations for third-party modules without TypeScript definitions
 */

// Cytoscape extensions
declare module 'cytoscape-cose-bilkent' {
  import cytoscape from 'cytoscape';
  const coseBilkent: cytoscape.Ext;
  export default coseBilkent;
}

declare module 'cytoscape-popper' {
  import cytoscape from 'cytoscape';
  const popper: cytoscape.Ext;
  export default popper;
}

// KaTeX (optional dependency for math rendering)
declare module 'katex' {
  interface KatexOptions {
    throwOnError?: boolean;
    displayMode?: boolean;
    errorColor?: string;
    macros?: Record<string, string>;
    colorIsTextColor?: boolean;
    maxSize?: number;
    maxExpand?: number;
    trust?: boolean;
    strict?: boolean | string;
  }
  const katex: {
    renderToString(tex: string, options?: KatexOptions): string;
    render(tex: string, element: HTMLElement, options?: KatexOptions): void;
  };
  export default katex;
}

declare module 'katex/dist/katex.min.css';

// Theme management
declare module 'next-themes' {
  import { ReactNode } from 'react';

  interface ThemeProviderProps {
    attribute?: string;
    defaultTheme?: string;
    enableSystem?: boolean;
    disableTransitionOnChange?: boolean;
    storageKey?: string;
    themes?: string[];
    forcedTheme?: string;
    enableColorScheme?: boolean;
    children?: ReactNode;
  }

  interface UseThemeProps {
    theme?: string;
    setTheme: (theme: string) => void;
    resolvedTheme?: string;
    themes: string[];
    systemTheme?: 'dark' | 'light';
  }

  export function useTheme(): UseThemeProps;
  export function ThemeProvider(props: ThemeProviderProps): JSX.Element;
}
