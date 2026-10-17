/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#070c18', // Deepest background
          900: '#0d1629', // Panel / card base
          850: '#121d36', // Card hover / table row alt
          800: '#1a2744', // Card border / input border
          700: '#24355c', // Prominent borders / divider
          600: '#344c80', // Secondary text / icons
          500: '#4865a8', // Muted text
        },
        sentinel: {
          cyan: '#06b6d4',
          teal: '#14b8a6',
          amber: '#f59e0b',
          rose: '#f43f5e',
          emerald: '#10b981',
          indigo: '#6366f1',
        }
      },
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'sans-serif',
        ],
        mono: [
          'JetBrains Mono',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Monaco',
          'Consolas',
          'monospace',
        ],
      },
    },
  },
  plugins: [],
}
