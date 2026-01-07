/**
 * Terminal Observatory Theme - Centralized Theme Constants
 *
 * This file is the single source of truth for all theme values.
 * Import from '@/theme/constants' to use these values.
 *
 * Usage examples:
 *   import { THEME, COLORS } from '@/theme/constants';
 *
 *   // Direct color access
 *   style={{ color: COLORS.phosphorGreen }}
 *
 *   // Via THEME object
 *   style={{ backgroundColor: THEME.colors.primary }}
 *
 *   // CSS variable style (for inline styles matching CSS vars)
 *   className="text-[var(--phosphor-green)]"
 */

// =============================================================================
// CORE COLOR PALETTE
// =============================================================================

/**
 * Terminal Observatory color palette
 * These are the primary brand colors used throughout the application.
 */
export const COLORS = {
  // Primary brand colors
  phosphorGreen: "#00ff9f",
  phosphorGreenDim: "#00ff9f80",
  phosphorGreenMuted: "#00ff9f33",
  phosphorGreenSubtle: "#00ff9f1a",

  amber: "#ffb700",
  amberDim: "#ffb70080",
  amberMuted: "#ffb70033",
  amberSubtle: "#ffb7001a",

  cyan: "#00d4ff",
  cyanDim: "#00d4ff80",
  cyanMuted: "#00d4ff33",
  cyanSubtle: "#00d4ff1a",

  // Status colors
  success: "#22c55e",
  successMuted: "#22c55e33",
  warning: "#f59e0b",
  warningMuted: "#f59e0b33",
  error: "#ef4444",
  errorMuted: "#ef444433",
  info: "#3b82f6",
  infoMuted: "#3b82f633",

  // Terminal backgrounds
  background: "#0a0a0f",
  surface: "#0d0d12",
  surfaceHover: "#141419",
  surfaceActive: "#1a1a20",
  elevated: "#1a1a20",

  // Terminal borders
  border: "#30363d",
  borderMuted: "#21262d",
  borderSubtle: "#161b22",

  // Terminal text
  text: "#ffffff",
  textMuted: "#8b949e",
  textSubtle: "#484f58",
  textDisabled: "#30363d",

  // Chart colors (for data visualization)
  chart1: "#00ff9f", // phosphor green
  chart2: "#00d4ff", // cyan
  chart3: "#ffb700", // amber
  chart4: "#a855f7", // purple
  chart5: "#ec4899", // pink
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
 * Use these for className strings: `text-[var(--phosphor-green)]`
 */
export const CSS_VARS = {
  // Primary colors
  phosphorGreen: "--phosphor-green",
  phosphorGreenDim: "--phosphor-green-dim",
  phosphorGreenMuted: "--phosphor-green-muted",

  amber: "--amber-gold",
  amberDim: "--amber-gold-dim",
  amberMuted: "--amber-gold-muted",

  cyan: "--cyan",
  cyanDim: "--cyan-dim",
  cyanMuted: "--cyan-muted",

  // Terminal backgrounds
  terminalBg: "--terminal-bg",
  terminalSurface: "--terminal-surface",
  terminalSurfaceHover: "--terminal-surface-hover",
  terminalElevated: "--terminal-elevated",

  // Terminal borders
  terminalBorder: "--terminal-border",
  terminalBorderMuted: "--terminal-border-muted",

  // Terminal text
  terminalText: "--terminal-text",
  terminalTextMuted: "--terminal-text-muted",
  terminalTextSubtle: "--terminal-text-subtle",
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
    fast: "150ms",
    normal: "200ms",
    slow: "300ms",
    verySlow: "500ms",
  },

  // Border radius
  radius: {
    none: "0",
    sm: "0.25rem",
    md: "0.375rem",
    lg: "0.5rem",
    xl: "0.75rem",
    "2xl": "1rem",
    "3xl": "1.5rem",
    full: "9999px",
  },

  // Spacing scale (matches Tailwind)
  spacing: {
    px: "1px",
    0: "0",
    0.5: "0.125rem",
    1: "0.25rem",
    1.5: "0.375rem",
    2: "0.5rem",
    2.5: "0.625rem",
    3: "0.75rem",
    3.5: "0.875rem",
    4: "1rem",
    5: "1.25rem",
    6: "1.5rem",
    7: "1.75rem",
    8: "2rem",
    9: "2.25rem",
    10: "2.5rem",
    12: "3rem",
    14: "3.5rem",
    16: "4rem",
  },

  // Font families
  fonts: {
    mono: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
    sans: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
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
 * @example cssVar('phosphorGreen') => 'var(--phosphor-green)'
 */
export const cssVar = (name: keyof typeof CSS_VARS): string =>
  `var(${CSS_VARS[name]})`;

/**
 * Get color with opacity
 * @example withOpacity(COLORS.phosphorGreen, 0.5) => '#00ff9f80'
 */
export const withOpacity = (color: string, opacity: number): string => {
  const hex = Math.round(opacity * 255).toString(16).padStart(2, '0');
  return `${color}${hex}`;
};

/**
 * Generate gradient string
 */
export const gradient = (
  direction: 'to-r' | 'to-l' | 'to-t' | 'to-b' | 'to-br' | 'to-bl' | 'to-tr' | 'to-tl',
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
  "--phosphor-green": COLORS.phosphorGreen,
  "--phosphor-green-dim": COLORS.phosphorGreenDim,
  "--phosphor-green-muted": COLORS.phosphorGreenMuted,

  "--amber-gold": COLORS.amber,
  "--amber-gold-dim": COLORS.amberDim,
  "--amber-gold-muted": COLORS.amberMuted,

  "--cyan": COLORS.cyan,
  "--cyan-dim": COLORS.cyanDim,
  "--cyan-muted": COLORS.cyanMuted,

  // Terminal theme
  "--terminal-bg": COLORS.background,
  "--terminal-surface": COLORS.surface,
  "--terminal-surface-hover": COLORS.surfaceHover,
  "--terminal-elevated": COLORS.elevated,
  "--terminal-border": COLORS.border,
  "--terminal-border-muted": COLORS.borderMuted,
  "--terminal-text": COLORS.text,
  "--terminal-text-muted": COLORS.textMuted,
  "--terminal-text-subtle": COLORS.textSubtle,
} as const;

// =============================================================================
// EXPORTS
// =============================================================================

export default THEME;
