/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Agricultural green, tuned so the 600/700 steps stay legible as text
        // on both the light wash and the dark surface.
        mandi: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
          950: '#052e16',
        },
        // Warm earth tone for accents, so the palette is not monochrome green.
        harvest: {
          100: '#fef3c7',
          300: '#fcd34d',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
        },
        // Near-black with a green cast rather than pure grey, so dark mode
        // still reads as part of the same product.
        soil: {
          50: '#f7f8f7',
          100: '#eceeec',
          200: '#d5dad6',
          300: '#b0b9b2',
          400: '#849289',
          500: '#65746b',
          600: '#4f5c55',
          700: '#414b46',
          800: '#1a201d',
          900: '#0f1411',
          950: '#080b09',
        },
      },
      fontFamily: {
        // Noto Sans Devanagari keeps Hindi legible at small sizes on Android,
        // where the default fallback is often poorly hinted.
        sans: [
          'Inter var', 'Inter', '-apple-system', 'BlinkMacSystemFont',
          'Noto Sans Devanagari', 'Noto Sans Bengali', 'Noto Sans Tamil',
          'system-ui', 'sans-serif',
        ],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      borderRadius: {
        '4xl': '2rem',
      },
      boxShadow: {
        card: '0 1px 2px rgb(16 24 20 / 0.04), 0 8px 24px -12px rgb(16 24 20 / 0.12)',
        lift: '0 2px 4px rgb(16 24 20 / 0.05), 0 20px 44px -20px rgb(16 24 20 / 0.22)',
        glow: '0 0 0 1px rgb(34 197 94 / 0.16), 0 12px 36px -12px rgb(34 197 94 / 0.34)',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(0.9)', opacity: '0.7' },
          '70%': { transform: 'scale(1.6)', opacity: '0' },
          '100%': { opacity: '0' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        },
      },
      animation: {
        // No fill mode: the resting state is visible, so if the animation never
        // runs the content is simply there.
        'fade-up': 'fade-up 0.5s cubic-bezier(0.22, 1, 0.36, 1)',
        shimmer: 'shimmer 1.8s infinite',
        'pulse-ring': 'pulse-ring 2s cubic-bezier(0.24, 0, 0.38, 1) infinite',
        float: 'float 6s ease-in-out infinite',
      },
      transitionTimingFunction: {
        smooth: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
    },
  },
  plugins: [],
};
