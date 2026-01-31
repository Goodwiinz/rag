/**
 * Module declarations for packages without type definitions
 */

declare module 'react-syntax-highlighter' {
  import { ComponentType, ReactNode } from 'react';
  
  export interface SyntaxHighlighterProps {
    children?: ReactNode;
    language?: string;
    style?: Record<string, React.CSSProperties>;
    showLineNumbers?: boolean;
    startingLineNumber?: number;
    lineNumberStyle?: React.CSSProperties | ((lineNumber: number) => React.CSSProperties);
    wrapLines?: boolean;
    wrapLongLines?: boolean;
    lineProps?: object | ((lineNumber: number) => object);
    customStyle?: React.CSSProperties;
    codeTagProps?: object;
    useInlineStyles?: boolean;
    PreTag?: keyof JSX.IntrinsicElements | ComponentType<unknown>;
    CodeTag?: keyof JSX.IntrinsicElements | ComponentType<unknown>;
    [key: string]: unknown;
  }

  export const Prism: ComponentType<SyntaxHighlighterProps>;
  export const Light: ComponentType<SyntaxHighlighterProps>;
  export const PrismLight: ComponentType<SyntaxHighlighterProps>;
  const SyntaxHighlighter: ComponentType<SyntaxHighlighterProps>;
  export default SyntaxHighlighter;
}

declare module 'react-syntax-highlighter/dist/esm/styles/prism' {
  const styles: { [key: string]: Record<string, React.CSSProperties> };
  export const atomDark: Record<string, React.CSSProperties>;
  export const vscDarkPlus: Record<string, React.CSSProperties>;
  export const oneDark: Record<string, React.CSSProperties>;
  export const materialDark: Record<string, React.CSSProperties>;
  export const dracula: Record<string, React.CSSProperties>;
  export const nord: Record<string, React.CSSProperties>;
  export const okaidia: Record<string, React.CSSProperties>;
  export const tomorrow: Record<string, React.CSSProperties>;
  export const twilight: Record<string, React.CSSProperties>;
  export const prism: Record<string, React.CSSProperties>;
  export default styles;
}

declare module 'react-syntax-highlighter/dist/esm/styles/hljs' {
  const styles: { [key: string]: Record<string, React.CSSProperties> };
  export const atomOneDark: Record<string, React.CSSProperties>;
  export const vs2015: Record<string, React.CSSProperties>;
  export const monokai: Record<string, React.CSSProperties>;
  export default styles;
}

declare module 'react-window' {
  import { ComponentType, CSSProperties, ReactNode, Ref } from 'react';

  export interface ListChildComponentProps<T = any> {
    index: number;
    style: CSSProperties;
    data: T;
    isScrolling?: boolean;
  }

  export interface FixedSizeListProps<T = any> {
    children: ComponentType<ListChildComponentProps<T>> | ComponentType<any>;
    className?: string;
    direction?: 'ltr' | 'rtl';
    height: number | string;
    initialScrollOffset?: number;
    innerRef?: Ref<HTMLElement>;
    innerElementType?: keyof JSX.IntrinsicElements | ComponentType<unknown>;
    itemCount: number;
    itemData?: T;
    itemKey?: (index: number, data: T) => string | number;
    itemSize: number;
    layout?: 'horizontal' | 'vertical';
    onItemsRendered?: (props: { overscanStartIndex: number; overscanStopIndex: number; visibleStartIndex: number; visibleStopIndex: number }) => void;
    onScroll?: (props: { scrollDirection: 'forward' | 'backward'; scrollOffset: number; scrollUpdateWasRequested: boolean }) => void;
    outerRef?: Ref<HTMLElement>;
    outerElementType?: keyof JSX.IntrinsicElements | ComponentType<unknown>;
    overscanCount?: number;
    style?: CSSProperties;
    useIsScrolling?: boolean;
    width: number | string;
  }

  export interface VariableSizeListProps<T = unknown> extends Omit<FixedSizeListProps<T>, 'itemSize'> {
    estimatedItemSize?: number;
    itemSize: (index: number) => number;
  }

  export interface FixedSizeListInstance {
    scrollTo(scrollOffset: number): void;
    scrollToItem(index: number, align?: 'auto' | 'smart' | 'center' | 'end' | 'start'): void;
  }

  export interface VariableSizeListInstance {
    scrollTo(scrollOffset: number): void;
    scrollToItem(index: number, align?: 'auto' | 'smart' | 'center' | 'end' | 'start'): void;
    resetAfterIndex(index: number, shouldForceUpdate?: boolean): void;
  }

  export class FixedSizeList<T = any> extends React.Component<FixedSizeListProps<T>> implements FixedSizeListInstance {
    scrollTo(scrollOffset: number): void;
    scrollToItem(index: number, align?: 'auto' | 'smart' | 'center' | 'end' | 'start'): void;
  }

  export class VariableSizeList<T = any> extends React.Component<VariableSizeListProps<T>> implements VariableSizeListInstance {
    scrollTo(scrollOffset: number): void;
    scrollToItem(index: number, align?: 'auto' | 'smart' | 'center' | 'end' | 'start'): void;
    resetAfterIndex(index: number, shouldForceUpdate?: boolean): void;
  }

  export interface GridChildComponentProps<T = unknown> {
    columnIndex: number;
    rowIndex: number;
    style: CSSProperties;
    data: T;
    isScrolling?: boolean;
  }

  export interface FixedSizeGridProps<T = unknown> {
    children: ComponentType<GridChildComponentProps<T>>;
    className?: string;
    columnCount: number;
    columnWidth: number;
    direction?: 'ltr' | 'rtl';
    height: number;
    initialScrollLeft?: number;
    initialScrollTop?: number;
    innerRef?: Ref<HTMLElement>;
    innerElementType?: keyof JSX.IntrinsicElements | ComponentType<unknown>;
    itemData?: T;
    itemKey?: (params: { columnIndex: number; rowIndex: number; data: T }) => string | number;
    onItemsRendered?: (props: {
      overscanColumnStartIndex: number;
      overscanColumnStopIndex: number;
      overscanRowStartIndex: number;
      overscanRowStopIndex: number;
      visibleColumnStartIndex: number;
      visibleColumnStopIndex: number;
      visibleRowStartIndex: number;
      visibleRowStopIndex: number;
    }) => void;
    onScroll?: (props: {
      horizontalScrollDirection: 'forward' | 'backward';
      scrollLeft: number;
      scrollTop: number;
      scrollUpdateWasRequested: boolean;
      verticalScrollDirection: 'forward' | 'backward';
    }) => void;
    outerRef?: Ref<HTMLElement>;
    outerElementType?: keyof JSX.IntrinsicElements | ComponentType<unknown>;
    overscanColumnCount?: number;
    overscanRowCount?: number;
    rowCount: number;
    rowHeight: number;
    style?: CSSProperties;
    useIsScrolling?: boolean;
    width: number;
  }

  export const FixedSizeGrid: React.ForwardRefExoticComponent<FixedSizeGridProps<unknown> & React.RefAttributes<{
    scrollTo(params: { scrollLeft?: number; scrollTop?: number }): void;
    scrollToItem(params: { align?: 'auto' | 'smart' | 'center' | 'end' | 'start'; columnIndex?: number; rowIndex?: number }): void;
  }>>;

  export function areEqual(prevProps: object, nextProps: object): boolean;
  export function shouldComponentUpdate(nextProps: object, nextState: object): boolean;
}

declare module 'msw/node' {
  export function setupServer(...handlers: unknown[]): {
    listen(options?: { onUnhandledRequest?: 'bypass' | 'warn' | 'error' }): void;
    close(): void;
    resetHandlers(...handlers: unknown[]): void;
    use(...handlers: unknown[]): void;
  };
}

declare module 'msw' {
  type RequestResolver = (info: { request: Request; params: Record<string, string> }) => Response | Promise<Response>;
  export const http: {
    get(path: string, resolver: RequestResolver): unknown;
    post(path: string, resolver: RequestResolver): unknown;
    put(path: string, resolver: RequestResolver): unknown;
    patch(path: string, resolver: RequestResolver): unknown;
    delete(path: string, resolver: RequestResolver): unknown;
    all(path: string, resolver: RequestResolver): unknown;
  };
  export const HttpResponse: {
    json<T>(data: T, init?: ResponseInit): Response;
    text(data: string, init?: ResponseInit): Response;
    xml(data: string, init?: ResponseInit): Response;
    arrayBuffer(data: ArrayBuffer, init?: ResponseInit): Response;
    formData(data: FormData, init?: ResponseInit): Response;
  };
  export function delay(ms: number): Promise<void>;
}

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

declare module 'd3' {
  export * from 'd3-array';
  export * from 'd3-color';
  export * from 'd3-ease';
  export * from 'd3-interpolate';
  export * from 'd3-path';
  export * from 'd3-scale';
  export * from 'd3-shape';
  export * from 'd3-time';
  export * from 'd3-timer';
  export * from 'd3-selection';
  export * from 'd3-drag';
  export * from 'd3-zoom';
  export * from 'd3-force';
  export * from 'd3-transition';
  
  // Additional types used in the codebase
  export interface DragBehavior<GElement extends Element, Datum, Subject> {
    (selection: Selection<GElement, Datum, unknown, unknown>, ...args: unknown[]): void;
    on(typenames: string, listener: null): this;
    on(typenames: string, listener: (this: GElement, event: unknown, d: Datum) => void): this;
    on(typenames: string): ((this: GElement, event: unknown, d: Datum) => void) | undefined;
  }
}

declare module 'next-themes' {
  import { ReactNode } from 'react';
  
  export interface ThemeProviderProps {
    children: ReactNode;
    themes?: string[];
    defaultTheme?: string;
    attribute?: string | 'class';
    value?: Record<string, string>;
    enableSystem?: boolean;
    enableColorScheme?: boolean;
    storageKey?: string;
    forcedTheme?: string;
    disableTransitionOnChange?: boolean;
  }

  export function ThemeProvider(props: ThemeProviderProps): JSX.Element;

  export interface UseThemeProps {
    themes: string[];
    theme?: string;
    setTheme: (theme: string) => void;
    forcedTheme?: string;
    resolvedTheme?: string;
    systemTheme?: 'dark' | 'light';
  }

  export function useTheme(): UseThemeProps;
}
