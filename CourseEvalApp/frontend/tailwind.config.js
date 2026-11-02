/** @type {import('tailwindcss').Config} */
// Design tokens for the Course Evaluation app.
// Colors are CSS variables (src/index.css) with a light and a dark set; the "dark" class on <html> switches them.
// Ink and paper for reading, one ocean blue for actions, and a low-to-high score scale
// (red -> amber -> green) that is always shown next to the number, never instead of it.
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
          lowTint: token('score-low-tint'), midTint: token('score-mid-tint'), highTint: token('score-high-tint'),
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
      // Short, quiet motion; all of it is switched off by the reduced-motion rule in index.css
      keyframes: {
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'fade-up': { from: { opacity: '0', transform: 'translateY(4px)' }, to: { opacity: '1', transform: 'none' } },
        'scale-in': { from: { opacity: '0', transform: 'scale(0.98)' }, to: { opacity: '1', transform: 'none' } },
        'grow-up': { from: { transform: 'scaleY(0)' }, to: { transform: 'scaleY(1)' } },
      },
      animation: {
        'fade-in': 'fade-in 180ms ease-out both',
        'fade-up': 'fade-up 260ms ease-out both',
        'scale-in': 'scale-in 180ms ease-out both',
        'grow-up': 'grow-up 500ms cubic-bezier(0.2, 0.7, 0.2, 1) both',
      },
    },
  },
  plugins: [],
};
