import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import PropTypes from 'prop-types';

const STORAGE_KEY = 'courseeval_theme';

const savedTheme = () => {
  try { return localStorage.getItem(STORAGE_KEY); } catch { return null; }
};

const systemTheme = () => (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');

export const applyTheme = (theme) => document.documentElement.classList.toggle('dark', theme === 'dark');

// Called before React renders so the page never flashes the wrong theme
export const initialTheme = () => {
  const theme = savedTheme() || systemTheme();
  applyTheme(theme);
  return theme;
};

// Colors for charts drawn in SVG, which can't read the CSS variables directly
export const CHART_COLORS = {
  light: { low: '#B42318', mid: '#B26B00', high: '#1E7A4F', accent: '#1E5A8A', grid: '#E2E3E0', axis: '#5F6670', ink: '#1C2128', paper: '#FFFFFF', series: ['#1E5A8A', '#1E7A4F', '#B26B00', '#6B4FA3', '#B42318', '#5F6670'] },
  dark: { low: '#F08A80', mid: '#E3A94B', high: '#5CC08E', accent: '#7FB3E0', grid: '#2E3238', axis: '#9AA1AA', ink: '#E7E9EC', paper: '#1B1E22', series: ['#7FB3E0', '#5CC08E', '#E3A94B', '#B9A3E8', '#F08A80', '#9AA1AA'] },
};

const ThemeContext = createContext({ theme: 'light', toggleTheme: () => {} });

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => (document.documentElement.classList.contains('dark') ? 'dark' : 'light'));

  useEffect(() => { applyTheme(theme); }, [theme]);

  // Follow the device setting until the person picks a theme themselves
  useEffect(() => {
    const query = window.matchMedia?.('(prefers-color-scheme: dark)');
    if (!query) return undefined;
    const follow = (event) => { if (!savedTheme()) setTheme(event.matches ? 'dark' : 'light'); };
    query.addEventListener('change', follow);
    return () => query.removeEventListener('change', follow);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((current) => {
      const next = current === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(STORAGE_KEY, next); } catch { /* not saved; still switches for this visit */ }
      return next;
    });
  }, []);

  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

ThemeProvider.propTypes = { children: PropTypes.node };

// eslint-disable-next-line react-refresh/only-export-components
export const useTheme = () => useContext(ThemeContext);

export function ThemeToggle({ className = '' }) {
  const { theme, toggleTheme } = useTheme();
  const dark = theme === 'dark';
  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-pressed={dark}
      className={`inline-flex items-center gap-2 text-xs font-medium text-ink-soft underline-offset-2 hover:text-ink hover:underline ${className}`}
    >
      <svg aria-hidden="true" viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="currentColor">
        {dark
          ? <path d="M8 1.5a.75.75 0 0 1 .75.75v1a.75.75 0 0 1-1.5 0v-1A.75.75 0 0 1 8 1.5Zm0 3.25a3.25 3.25 0 1 1 0 6.5 3.25 3.25 0 0 1 0-6.5Zm5.75 2.5a.75.75 0 0 1 0 1.5h-1a.75.75 0 0 1 0-1.5h1Zm-10.5 0a.75.75 0 0 1 0 1.5h-1a.75.75 0 0 1 0-1.5h1ZM8 12a.75.75 0 0 1 .75.75v1a.75.75 0 0 1-1.5 0v-1A.75.75 0 0 1 8 12Z" />
          : <path d="M6.2 1.6a.6.6 0 0 1 .1.66A5.5 5.5 0 0 0 13.74 9.7a.6.6 0 0 1 .79.73A6.75 6.75 0 1 1 5.57 1.47a.6.6 0 0 1 .63.13Z" />}
      </svg>
      {dark ? 'Light mode' : 'Dark mode'}
    </button>
  );
}

ThemeToggle.propTypes = { className: PropTypes.string };
