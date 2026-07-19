/**
 * NOUS Brand Theme - Centralized Theme Constants
 *
 * This file is the single source of truth for all theme values.
 * Import from '@/theme/constants' to use these values.
 *
 * Brand palette:
 *   Erebus  #0A0A0E — deep black (backgrounds)
 *   Selene  #F7F7F5 — warm white (text on dark)
 *   Sol     #D4A039 — gold (primary accent)
 *   Helios  #E8B84A — warm gold (secondary accent)
 *   Apollo  #F5D680 — light gold (highlights)
 */

// =============================================================================
// CORE COLOR PALETTE
// =============================================================================

// NOTE: values remapped onto the NOUS "Observatory" brand palette (2026-05-31).
// Keys are unchanged so every consumer updates for free. The legacy "phosphor"/
// "cyan"/"terminal" key names are kept only for backward-compat; the VALUES are
// brand tokens now (One Voice gold accent, warm-dark surfaces, no pure white,
// no cold blue-grey). Don't reintroduce the old terminal/cyan hexes.
export const COLORS = {
  // NOUS brand accent (Sol / Helios / Apollo)
  phosphorGreen: '#D4A039',
  phosphorGreenDim: '#D4A03980',
  phosphorGreenMuted: '#D4A03933',
  phosphorGreenSubtle: '#D4A0391a',

  amber: '#E8B84A',
  amberDim: '#E8B84A80',
  amberMuted: '#E8B84A33',
  amberSubtle: '#E8B84A1a',

  // Legacy "cyan" secondary collapsed onto the single gold accent (One Voice).
  cyan: '#D4A039',
  cyanDim: '#D4A03980',
  cyanMuted: '#D4A03933',
  cyanSubtle: '#D4A0391a',

  // Status colors — brand semantic signal (Terra / Corona / Mars); info → neutral.
  success: '#34d399',
  successMuted: '#34d39933',
  warning: '#f59e0b',
  warningMuted: '#f59e0b33',
  error: '#ef4444',
  errorMuted: '#ef444433',
  info: '#8a8070',
  infoMuted: '#8a807033',

  // Warm-dark surfaces (Nyx → Umber depth stack), not cold blue-grey.
  background: '#141210',
  surface: '#1e1b17',
  surfaceHover: '#28241e',
  surfaceActive: '#332e26',
  elevated: '#28241e',

  // Warm borders (Shade family).
  border: '#2a261f',
  borderMuted: '#28241e',
  borderSubtle: '#1e1b17',

  // Warm ivory text — never pure white.
  text: '#f5f0e8',
  textMuted: '#c8bfa8',
  textSubtle: '#8a8070',
  textDisabled: '#524c42',

  // Chart colors (data viz is the one sanctioned multi-hue zone; curated + warm).
  chart1: '#D4A039', // Sol gold
  chart2: '#0e7490', // deep teal
  chart3: '#E8B84A', // Helios
  chart4: '#b45309', // burnt amber
  chart5: '#9f1239', // deep rose
} as const;

// =============================================================================
// SEMANTIC COLOR MAPPINGS
// =============================================================================

/**
 * Semantic color mappings for common use cases.
 * Use these when the color represents a semantic meaning.
 */
export const SEMANTIC_COLORS = {
  // User vs Assistant messaging
  user: COLORS.amber,
  userMuted: COLORS.amberMuted,
  assistant: COLORS.phosphorGreen,
  assistantMuted: COLORS.phosphorGreenMuted,

  // Interactive states
  interactive: COLORS.phosphorGreen,
  interactiveHover: COLORS.phosphorGreenDim,
  interactiveMuted: COLORS.phosphorGreenMuted,

  // Accent/highlight
  accent: COLORS.amber,
  accentHover: COLORS.amberDim,
  accentMuted: COLORS.amberMuted,

  // Secondary actions
  secondary: COLORS.cyan,
  secondaryHover: COLORS.cyanDim,
  secondaryMuted: COLORS.cyanMuted,

  // Links
  link: COLORS.cyan,
  linkHover: COLORS.phosphorGreen,

  // Processing/loading states
  processing: COLORS.cyan,
  streaming: COLORS.phosphorGreen,
  pending: COLORS.amber,
} as const;

// =============================================================================
// CSS VARIABLE NAMES
// =============================================================================

/**
 * CSS variable names matching the values defined in globals.css
 * Use these for className strings: `text-[var(--nous-sol)]`
 */
export const CSS_VARS = {
  // Primary colors
  phosphorGreen: '--nous-sol',
  phosphorGreenDim: '--nous-helios',
  phosphorGreenMuted: '--nous-sol-muted',

  amber: '--nous-helios',
  amberDim: '--nous-sol',
  amberMuted: '--nous-helios-muted',

  cyan: '--nous-helios',
  cyanDim: '--nous-helios-muted',
  cyanMuted: '--nous-sol-muted',

  // Terminal backgrounds
  terminalBg: '--nous-bg-1',
  terminalSurface: '--nous-bg-2',
  terminalSurfaceHover: '--nous-bg-3',
  terminalElevated: '--nous-bg-3',

  // Terminal borders
  terminalBorder: '--nous-border-1',
  terminalBorderMuted: '--nous-border-2',

  // Terminal text
  terminalText: '--nous-fg-1',
  terminalTextMuted: '--nous-fg-3',
  terminalTextSubtle: '--nous-fg-3',
} as const;

// =============================================================================
// MAIN THEME OBJECT
// =============================================================================

/**
 * Main THEME object - the primary export for theme values.
 * This maintains backward compatibility with existing imports.
 */
export const THEME = {
  colors: {
    // Primary brand colors (Terminal Observatory palette)
    primary: COLORS.phosphorGreen,
    primaryDim: COLORS.phosphorGreenDim,
    primaryMuted: COLORS.phosphorGreenMuted,

    accent: COLORS.amber,
    accentDim: COLORS.amberDim,
    accentMuted: COLORS.amberMuted,

    secondary: COLORS.cyan,
    secondaryDim: COLORS.cyanDim,
    secondaryMuted: COLORS.cyanMuted,

    // Status colors
    success: COLORS.success,
    successMuted: COLORS.successMuted,
    warning: COLORS.warning,
    warningMuted: COLORS.warningMuted,
    error: COLORS.error,
    errorMuted: COLORS.errorMuted,
    info: COLORS.info,
    infoMuted: COLORS.infoMuted,

    // Backgrounds
    background: COLORS.background,
    surface: COLORS.surface,
    card: COLORS.surface, // Alias for surface
    surfaceHover: COLORS.surfaceHover,
    surfaceActive: COLORS.surfaceActive,
    elevated: COLORS.elevated,

    // Borders
    border: COLORS.border,
    borderMuted: COLORS.borderMuted,
    borderSubtle: COLORS.borderSubtle,

    // Text
    text: COLORS.text,
    textMuted: COLORS.textMuted,
    textSubtle: COLORS.textSubtle,
    textDisabled: COLORS.textDisabled,

    // Chart colors
    chart1: COLORS.chart1,
    chart2: COLORS.chart2,
    chart3: COLORS.chart3,
    chart4: COLORS.chart4,
    chart5: COLORS.chart5,
  },

  // Animation durations
  transitions: {
    fast: '150ms',
    normal: '200ms',
    slow: '300ms',
    verySlow: '500ms',
  },

  // Border radius
  radius: {
    none: '0',
    sm: '0.25rem',
    md: '0.375rem',
    lg: '0.5rem',
    xl: '0.75rem',
    '2xl': '1rem',
    '3xl': '1.5rem',
    full: '9999px',
  },

  // Spacing scale (matches Tailwind)
  spacing: {
    px: '1px',
    0: '0',
    0.5: '0.125rem',
    1: '0.25rem',
    1.5: '0.375rem',
    2: '0.5rem',
    2.5: '0.625rem',
    3: '0.75rem',
    3.5: '0.875rem',
    4: '1rem',
    5: '1.25rem',
    6: '1.5rem',
    7: '1.75rem',
    8: '2rem',
    9: '2.25rem',
    10: '2.5rem',
    12: '3rem',
    14: '3.5rem',
    16: '4rem',
  },

  // Font families
  fonts: {
    mono: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
    sans: "'Inter', system-ui, -apple-system, sans-serif",
    serif: "'Source Serif 4', Georgia, serif",
  },
} as const;

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Type-safe color getter
 */
export type ThemeColor = keyof typeof THEME.colors;
export const getColor = (color: ThemeColor): string => THEME.colors[color];

/**
 * Get CSS variable reference for use in className strings
 * @example cssVar('phosphorGreen') => 'var(--nous-sol)'
 */
export const cssVar = (name: keyof typeof CSS_VARS): string =>
  `var(${CSS_VARS[name]})`;

/**
 * Get color with opacity
 * @example withOpacity(COLORS.phosphorGreen, 0.5) => '#D4A03980'
 */
export const withOpacity = (color: string, opacity: number): string => {
  const hex = Math.round(opacity * 255)
    .toString(16)
    .padStart(2, '0');
  return `${color}${hex}`;
};

/**
 * Generate gradient string
 */
export const gradient = (
  direction:
    | 'to-r'
    | 'to-l'
    | 'to-t'
    | 'to-b'
    | 'to-br'
    | 'to-bl'
    | 'to-tr'
    | 'to-tl',
  from: string,
  to: string,
  via?: string
): string => {
  const dir = direction.replace('-', ' ');
  if (via) {
    return `linear-gradient(${dir}, ${from}, ${via}, ${to})`;
  }
  return `linear-gradient(${dir}, ${from}, ${to})`;
};

// =============================================================================
// CSS VARIABLE MAPPING (for globals.css)
// =============================================================================

/**
 * CSS variable definitions that should be added to globals.css
 * This is exported for reference and automated CSS generation.
 */
export const cssVariableDefinitions = {
  // Primary colors
  '--nous-sol': COLORS.phosphorGreen,
  '--nous-helios': COLORS.phosphorGreenDim,
  '--nous-sol-muted': COLORS.phosphorGreenMuted,
  '--nous-helios-muted': COLORS.amberMuted,

  // Surfaces and text
  '--nous-bg-1': COLORS.background,
  '--nous-bg-2': COLORS.surface,
  '--nous-bg-3': COLORS.elevated,
  '--nous-border-1': COLORS.border,
  '--nous-border-2': COLORS.borderMuted,
  '--nous-fg-1': COLORS.text,
  '--nous-fg-3': COLORS.textMuted,
} as const;

// =============================================================================
// EXPORTS
// =============================================================================

export default THEME;
