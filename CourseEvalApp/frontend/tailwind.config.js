/** @type {import('tailwindcss').Config} */
// Design tokens for the Course Evaluation app (Phase 5).
// Ink and paper for reading, one academic blue for actions, and a low-to-high score scale
// (oxblood -> slate -> pine) that is always shown next to the number, never instead of it.
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        serif: ['"IBM Plex Serif"', 'Georgia', 'serif'],
      },
      colors: {
        ink: { DEFAULT: '#1B2533', soft: '#3D4756', muted: '#6B7482' },
        paper: '#FFFFFF',
        page: '#F4F6F8',
        line: { DEFAULT: '#DCE1E7', soft: '#EBEEF2' },
        accent: { DEFAULT: '#1F4E79', dark: '#173B5C', tint: '#E8EFF6' },
        score: { low: '#9B2C2C', mid: '#5B6573', high: '#1F6F5C', lowTint: '#F6E9E9', highTint: '#E6F1EE' },
      },
      fontSize: {
        // Modular scale (ratio ~1.2) on a 15px base for dense reading
        xs: ['0.75rem', { lineHeight: '1.1rem' }],
        sm: ['0.8125rem', { lineHeight: '1.25rem' }],
        base: ['0.9375rem', { lineHeight: '1.5rem' }],
        lg: ['1.125rem', { lineHeight: '1.65rem' }],
        xl: ['1.35rem', { lineHeight: '1.8rem' }],
        '2xl': ['1.62rem', { lineHeight: '2.05rem' }],
        '3xl': ['1.95rem', { lineHeight: '2.35rem' }],
        '5xl': ['3.25rem', { lineHeight: '1' }],
      },
    },
  },
  plugins: [],
};
