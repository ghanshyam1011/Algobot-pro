/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // AlgoBot brand colours
        brand: {
          50:  '#eef2ff',
          100: '#e0e7ff',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          900: '#1e1b4b',
        },
        buy:  { DEFAULT: '#22c55e', dark: '#16a34a', light: '#f0fdf4' },
        sell: { DEFAULT: '#ef4444', dark: '#dc2626', light: '#fef2f2' },
        hold: { DEFAULT: '#f59e0b', dark: '#d97706', light: '#fffbeb' },
        // Dark theme surfaces
        dark: {
          bg:      '#0f1117',
          surface: '#1a1d27',
          card:    '#1e2130',
          border:  '#2a2d3e',
          hover:   '#252838',
          muted:   '#6b7280',
        },
        // Light theme surfaces
        light: {
          bg:      '#f8fafc',
          surface: '#ffffff',
          card:    '#ffffff',
          border:  '#e2e8f0',
          hover:   '#f1f5f9',
          muted:   '#94a3b8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-in':   'slideIn 0.2s ease-out',
        'fade-in':    'fadeIn 0.3s ease-out',
      },
      keyframes: {
        slideIn: {
          '0%':   { transform: 'translateY(-8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)',    opacity: '1' },
        },
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};