export const theme = {
  colors: {
    primary: {
      default: "hsl(var(--primary))",
      foreground: "hsl(var(--primary-foreground))",
    },
    secondary: {
      default: "hsl(var(--secondary))",
      foreground: "hsl(var(--secondary-foreground))",
    },
    destructive: {
      default: "hsl(var(--destructive))",
      foreground: "hsl(var(--destructive-foreground))",
    },
    background: "hsl(var(--background))",
    foreground: "hsl(var(--foreground))",
    muted: {
      default: "hsl(var(--muted))",
      foreground: "hsl(var(--muted-foreground))",
    },
    accent: {
      default: "hsl(var(--accent))",
      foreground: "hsl(var(--accent-foreground))",
    },
  },
  spacing: {
    1: "0.25rem",
    2: "0.5rem",
    3: "0.75rem",
    4: "1rem",
    5: "1.25rem",
    6: "1.5rem",
    8: "2rem",
    10: "2.5rem",
    12: "3rem",
    16: "4rem",
  },
  borderRadius: {
    sm: "calc(var(--radius) - 4px)",
    md: "calc(var(--radius) - 2px)",
    lg: "var(--radius)",
    full: "9999px",
  },
  animation: {
    fast: "200ms cubic-bezier(0.4, 0, 0.2, 1)",
    medium: "300ms cubic-bezier(0.4, 0, 0.2, 1)",
    slow: "500ms cubic-bezier(0.4, 0, 0.2, 1)",
  },
} as const;

export type Theme = typeof theme;
