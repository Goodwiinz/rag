import type { Config } from 'tailwindcss';
import tailwindcssAnimate from 'tailwindcss-animate';

const config: Config = {
  darkMode: ['class'],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        // NOUS brand colors — CSS vars adapt to light/dark automatically
        sol: 'var(--phosphor-green)',
        'sol-dim': 'var(--phosphor-green-dim)',
        'sol-muted': 'var(--phosphor-green-muted)',
        helios: 'var(--amber-gold)',
        'helios-dim': 'var(--amber-gold-dim)',
        'helios-muted': 'var(--amber-gold-muted)',
        'brand-cyan': 'var(--cyan)',
        'brand-cyan-dim': 'var(--cyan-dim)',
        'brand-cyan-muted': 'var(--cyan-muted)',
        // Terminal surfaces
        'terminal-bg': 'var(--terminal-bg)',
        'terminal-surface': 'var(--terminal-surface)',
        'terminal-surface-hover': 'var(--terminal-surface-hover)',
        'terminal-elevated': 'var(--terminal-elevated)',
        'terminal-border': 'var(--terminal-border)',
        'terminal-border-muted': 'var(--terminal-border-muted)',
        'terminal-text': 'var(--terminal-text)',
        'terminal-text-muted': 'var(--terminal-text-muted)',
        'terminal-text-subtle': 'var(--terminal-text-subtle)',
        sidebar: {
          DEFAULT: 'var(--sidebar-background)',
          foreground: 'var(--sidebar-foreground)',
          primary: 'var(--sidebar-primary)',
          'primary-foreground': 'var(--sidebar-primary-foreground)',
          accent: 'var(--sidebar-accent)',
          'accent-foreground': 'var(--sidebar-accent-foreground)',
          border: 'var(--sidebar-border)',
          ring: 'var(--sidebar-ring)',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      // NOUS type families — without these the `font-nous-*` utilities used
      // across the chat composer / command output / slash menu silently fall
      // back to sans-serif.
      fontFamily: {
        'nous-mono': ['var(--nous-font-mono)'],
        'nous-body': ['var(--nous-font-body)'],
        'nous-ui': ['var(--nous-font-ui)'],
        'nous-heading': ['var(--nous-font-heading)'],
      },
    },
  },
  plugins: [tailwindcssAnimate],
};

export default config;
