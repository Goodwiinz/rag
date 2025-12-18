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
  		padding: '2rem',
  		screens: {
  			'2xl': '1400px'
  		}
  	},
  	extend: {
  		colors: {
  			border: 'var(--border)',
  			input: 'var(--input)',
  			ring: 'var(--ring)',
  			background: 'var(--background)',
  			foreground: 'var(--foreground)',
  			primary: {
  				DEFAULT: 'var(--primary)',
  				foreground: 'var(--primary-foreground)'
  			},
  			secondary: {
  				DEFAULT: 'var(--secondary)',
  				foreground: 'var(--secondary-foreground)'
  			},
  			destructive: {
  				DEFAULT: 'var(--destructive)',
  				foreground: 'var(--destructive-foreground)'
  			},
  			muted: {
  				DEFAULT: 'var(--muted)',
  				foreground: 'var(--muted-foreground)'
  			},
  			accent: {
  				DEFAULT: 'var(--accent)',
  				foreground: 'var(--accent-foreground)'
  			},
  			popover: {
  				DEFAULT: 'var(--popover)',
  				foreground: 'var(--popover-foreground)'
  			},
  			card: {
  				DEFAULT: 'var(--card)',
  				foreground: 'var(--card-foreground)'
  			},
  			entity: {
  				person: '#3B82F6',
  				organization: '#10B981',
  				location: '#F59E0B',
  				concept: '#8B5CF6',
  				technology: '#EC4899',
  				event: '#14B8A6',
  				product: '#F97316'
  			},
  			processing: {
  				pending: '#94A3B8',
  				running: '#3B82F6',
  				completed: '#10B981',
  				failed: '#EF4444',
  				cancelled: '#6B7280'
  			},
  			sidebar: {
  				DEFAULT: 'hsl(var(--sidebar-background))',
  				foreground: 'hsl(var(--sidebar-foreground))',
  				primary: 'hsl(var(--sidebar-primary))',
  				'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
  				accent: 'hsl(var(--sidebar-accent))',
  				'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
  				border: 'hsl(var(--sidebar-border))',
  				ring: 'hsl(var(--sidebar-ring))'
  			}
  		},
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		fontFamily: {
  			sans: [
  				'var(--font-sans)',
  				'system-ui',
  				'sans-serif'
  			],
  			mono: [
  				'var(--font-mono)',
  				'monospace'
  			]
  		},
  		keyframes: {
  			'accordion-down': {
  				from: {
  					height: '0'
  				},
  				to: {
  					height: 'var(--radix-accordion-content-height)'
  				}
  			},
  			'accordion-up': {
  				from: {
  					height: 'var(--radix-accordion-content-height)'
  				},
  				to: {
  					height: '0'
  				}
  			},
  			'fade-in': {
  				from: {
  					opacity: '0',
  					transform: 'translateY(10px)'
  				},
  				to: {
  					opacity: '1',
  					transform: 'translateY(0)'
  				}
  			},
  			'fade-out': {
  				from: {
  					opacity: '1',
  					transform: 'translateY(0)'
  				},
  				to: {
  					opacity: '0',
  					transform: 'translateY(10px)'
  				}
  			},
  			'slide-in': {
  				from: {
  					opacity: '0',
  					transform: 'translateX(-20px)'
  				},
  				to: {
  					opacity: '1',
  					transform: 'translateX(0)'
  				}
  			},
  			'pulse-soft': {
  				'0%, 100%': {
  					opacity: '1'
  				},
  				'50%': {
  					opacity: '0.8'
  				}
  			},
  			shimmer: {
  				'0%': {
  					transform: 'translateX(-100%)'
  				},
  				'100%': {
  					transform: 'translateX(100%)'
  				}
  			},
  			blob: {
  				'0%': {
  					transform: 'translate(0px, 0px) scale(1)'
  				},
  				'33%': {
  					transform: 'translate(30px, -50px) scale(1.1)'
  				},
  				'66%': {
  					transform: 'translate(-20px, 20px) scale(0.9)'
  				},
  				'100%': {
  					transform: 'translate(0px, 0px) scale(1)'
  				}
  			}
  		},
  		animation: {
  			'accordion-down': 'accordion-down 0.2s ease-out',
  			'accordion-up': 'accordion-up 0.2s ease-out',
  			'fade-in': 'fade-in 0.4s ease-out',
  			'fade-out': 'fade-out 0.4s ease-out',
  			'slide-in': 'slide-in 0.4s ease-out',
  			'pulse-soft': 'pulse-soft 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
  			shimmer: 'shimmer 2s infinite',
  			blob: 'blob 7s infinite'
  		}
  	}
  },
  plugins: [
    require("tailwindcss-animate"),
    // Plugin for knowledge graph visualizations
    function ({ addUtilities, theme }) {
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