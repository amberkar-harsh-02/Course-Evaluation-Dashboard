import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import PropTypes from 'prop-types';
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-sans/600.css';
import '@fontsource/ibm-plex-serif/400.css';
import '@fontsource/ibm-plex-serif/500.css';
import './index.css';

import { AuthProvider, useAuth } from './auth';
import { ThemeProvider, initialTheme } from './theme';
import { ReportNavProvider } from './reportNav';
import Layout from './components/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import Reports from './pages/Reports';
import NewAnalysis from './pages/NewAnalysis';
import ReportView from './pages/ReportView';
import Compare from './pages/Compare';
import Account from './pages/Account';
import AdminUsers from './pages/AdminUsers';
import AdminUsage from './pages/AdminUsage';
import Guide from './pages/Guide';

function RequireAuth({ children, admin = false }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="p-8 text-sm text-ink-muted">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (admin && user.role !== 'admin') return <Navigate to="/" replace />;
  // A professor's first visit opens the Guide; the Guide records that it was seen
  if (user.role !== 'admin' && !user.guide_seen_at && location.pathname !== '/guide') return <Navigate to="/guide" replace />;
  return children;
}

RequireAuth.propTypes = { children: PropTypes.node, admin: PropTypes.bool };

initialTheme();

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider>
    <BrowserRouter basename="/course-eval-app">
      <AuthProvider>
        <Toaster position="bottom-right" toastOptions={{ className: 'text-sm' }} />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<RequireAuth><ReportNavProvider><Layout /></ReportNavProvider></RequireAuth>}>
            <Route index element={<Reports />} />
            <Route path="new" element={<NewAnalysis />} />
            <Route path="guide" element={<Guide />} />
            <Route path="account" element={<Account />} />
            <Route path="compare" element={<Compare />} />
            <Route path="reports/:reportId" element={<ReportView />} />
            <Route path="admin/users" element={<RequireAuth admin><AdminUsers /></RequireAuth>} />
            <Route path="admin/usage" element={<RequireAuth admin><AdminUsage /></RequireAuth>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
    </ThemeProvider>
  </StrictMode>,
);
