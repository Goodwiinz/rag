/**
 * useTheme Hook - React hook for accessing theme values
 *
 * Usage:
 *   import { useTheme } from '@/theme/useTheme';
 *
 *   function MyComponent() {
 *     const { colors, getStatusColor, getUserColor } = useTheme();
 *     return <div style={{ color: colors.primary }}>...</div>;
 *   }
 */

import { THEME, COLORS, SEMANTIC_COLORS, getColor, cssVar, withOpacity, CSS_VARS } from "./constants";

export function useTheme() {
  return {
    // Direct access to theme values
    colors: THEME.colors,
    transitions: THEME.transitions,
    radius: THEME.radius,
    spacing: THEME.spacing,
    fonts: THEME.fonts,

    // Raw color palette
    palette: COLORS,

    // Semantic colors
    semantic: SEMANTIC_COLORS,

    // Utility functions
    getColor,
    cssVar,
    withOpacity,

    // CSS variable names
    cssVars: CSS_VARS,

    /**
     * Get status color based on status type
     */
    getStatusColor: (status: "success" | "warning" | "error" | "info") => {
      const map = {
        success: THEME.colors.success,
        warning: THEME.colors.warning,
        error: THEME.colors.error,
        info: THEME.colors.info,
      };
      return map[status];
    },

    /**
     * Get muted status color
     */
    getStatusColorMuted: (status: "success" | "warning" | "error" | "info") => {
      const map = {
        success: THEME.colors.successMuted,
        warning: THEME.colors.warningMuted,
        error: THEME.colors.errorMuted,
        info: THEME.colors.infoMuted,
      };
      return map[status];
    },

    /**
     * Get color for user/assistant roles
     */
    getRoleColor: (role: "user" | "assistant") => {
      return role === "user" ? SEMANTIC_COLORS.user : SEMANTIC_COLORS.assistant;
    },

    /**
     * Get muted role color
     */
    getRoleColorMuted: (role: "user" | "assistant") => {
      return role === "user" ? SEMANTIC_COLORS.userMuted : SEMANTIC_COLORS.assistantMuted;
    },

    /**
     * Get processing state color
     */
    getProcessingColor: (state: "pending" | "processing" | "streaming" | "complete" | "error") => {
      const map = {
        pending: SEMANTIC_COLORS.pending,
        processing: SEMANTIC_COLORS.processing,
        streaming: SEMANTIC_COLORS.streaming,
        complete: THEME.colors.success,
        error: THEME.colors.error,
      };
      return map[state];
    },

    /**
     * Get chart colors array for data visualization
     */
    getChartColors: (count: number = 5) => {
      const chartColors = [
        THEME.colors.chart1,
        THEME.colors.chart2,
        THEME.colors.chart3,
        THEME.colors.chart4,
        THEME.colors.chart5,
      ];
      return chartColors.slice(0, count);
    },
  };
}

// Re-export for convenience
export { THEME, COLORS, SEMANTIC_COLORS, CSS_VARS, getColor, cssVar, withOpacity };
