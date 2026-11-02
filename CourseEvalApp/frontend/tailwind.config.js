/** @type {import('tailwindcss').Config} */
// Design tokens for the Course Evaluation app.
// Colors are CSS variables (src/index.css) with a light and a dark set; the "dark" class on <html> switches them.
// Ink and paper for reading, one academic blue for actions, and a low-to-high score scale
// (oxblood -> slate -> pine) that is always shown next to the number, never instead of it.
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        serif: ['"IBM Plex Serif"', 'Georgia', 'serif'],
      },
      colors: {
        ink: { DEFAULT: token('ink'), soft: token('ink-soft'), muted: token('ink-muted') },
        paper: token('paper'),
        page: token('page'),
        line: { DEFAULT: token('line'), soft: token('line-soft'), strong: token('line-strong') },
        accent: { DEFAULT: token('accent'), dark: token('accent-dark'), tint: token('accent-tint'), on: token('on-accent') },
        score: {
          low: token('score-low'), mid: token('score-mid'), high: token('score-high'),
          lowTint: token('score-low-tint'), highTint: token('score-high-tint'),
        },
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
