/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        sidebar:      '#0A0E1A',
        'sidebar-hover': '#16203A',
        accent:       '#6C63FF',
        'accent-dark':'#5B52F0',
        accent2:      '#A78BFA',
        teal:         '#0D9488',
        green:        '#22C55E',
        pending:      '#D97706',
        'card-dark':  '#1A1F2E',
        'bg-dark':    '#0F1117',
        'border-dark':'#2D3142',
        'card-light': '#FFFFFF',
        'bg-light':   '#F0F2FA',
        'border-light':'#E4E7EF',
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['Consolas', 'Cascadia Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
