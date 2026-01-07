/**
 * Theme Module - Centralized theme exports
 *
 * Import from '@/theme' for convenience:
 *   import { THEME, COLORS, useTheme } from '@/theme';
 */

// Core constants
export {
  THEME,
  COLORS,
  SEMANTIC_COLORS,
  CSS_VARS,
  cssVariableDefinitions,
  getColor,
  cssVar,
  withOpacity,
  gradient,
} from "./constants";

export type { ThemeColor } from "./constants";

// React hook
export { useTheme } from "./useTheme";

// Default export
export { default } from "./constants";
