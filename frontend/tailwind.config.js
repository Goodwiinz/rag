/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Knowledge graph specific colors
        entity: {
          person: "#3B82F6",
          organization: "#10B981",
          location: "#F59E0B",
          concept: "#8B5CF6",
          technology: "#EC4899",
          event: "#14B8A6",
          product: "#F97316",
        },
        // Processing status colors
        processing: {
          pending: "#94A3B8",
          running: "#3B82F6",
          completed: "#10B981",
          failed: "#EF4444",
          cancelled: "#6B7280",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "fade-in": {
          from: { opacity: "0", transform: "translateY(-10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in": {
          from: { opacity: "0", transform: "translateX(-20px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.8" },
        },
        "shimmer": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
        "bounce-subtle": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-5px)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "fade-in": "fade-in 0.3s ease-out",
        "slide-in": "slide-in 0.3s ease-out",
        "pulse-soft": "pulse-soft 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "shimmer": "shimmer 2s infinite",
        "bounce-subtle": "bounce-subtle 2s infinite",
      },
    },
  },
  plugins: [
    require("tailwindcss-animate"),
    // Plugin for knowledge graph visualizations
    function({ addUtilities, theme }) {
      const newUtilities = {
        ".graph-node-person": {
          backgroundColor: theme("colors.entity.person"),
          color: "white",
        },
        ".graph-node-organization": {
          backgroundColor: theme("colors.entity.organization"),
          color: "white",
        },
        ".graph-node-location": {
          backgroundColor: theme("colors.entity.location"),
          color: "white",
        },
        ".graph-node-concept": {
          backgroundColor: theme("colors.entity.concept"),
          color: "white",
        },
        ".graph-node-technology": {
          backgroundColor: theme("colors.entity.technology"),
          color: "white",
        },
        ".graph-node-event": {
          backgroundColor: theme("colors.entity.event"),
          color: "white",
        },
        ".graph-node-product": {
          backgroundColor: theme("colors.entity.product"),
          color: "white",
        },
        // Processing status animations
        ".processing-pending": {
          backgroundColor: theme("colors.processing.pending"),
        },
        ".processing-running": {
          backgroundColor: theme("colors.processing.running"),
          animation: "pulse-soft 2s infinite",
        },
        ".processing-completed": {
          backgroundColor: theme("colors.processing.completed"),
        },
        ".processing-failed": {
          backgroundColor: theme("colors.processing.failed"),
        },
        // File type specific styles
        ".file-pdf": {
          borderColor: theme("colors.red.500"),
          backgroundColor: theme("colors.red.50"),
        },
        ".file-text": {
          borderColor: theme("colors.blue.500"),
          backgroundColor: theme("colors.blue.50"),
        },
        ".file-image": {
          borderColor: theme("colors.green.500"),
          backgroundColor: theme("colors.green.50"),
        },
        ".file-video": {
          borderColor: theme("colors.purple.500"),
          backgroundColor: theme("colors.purple.50"),
        },
        ".file-audio": {
          borderColor: theme("colors.orange.500"),
          backgroundColor: theme("colors.orange.50"),
        },
      };
      addUtilities(newUtilities);
    },
  ],
};