import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import PropTypes from 'prop-types';
import './index.css';

import { AuthProvider, useAuth } from './auth';
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

function RequireAuth({ children, admin = false }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8 text-sm text-slate-500">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (admin && user.role !== 'admin') return <Navigate to="/" replace />;
  return children;
}

RequireAuth.propTypes = { children: PropTypes.node, admin: PropTypes.bool };

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter basename="/course-eval-app">
      <AuthProvider>
        <Toaster position="bottom-right" toastOptions={{ className: 'text-sm' }} />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<RequireAuth><Layout /></RequireAuth>}>
            <Route index element={<Reports />} />
            <Route path="new" element={<NewAnalysis />} />
            <Route path="account" element={<Account />} />
            <Route path="compare" element={<Compare />} />
            <Route path="admin/users" element={<RequireAuth admin><AdminUsers /></RequireAuth>} />
            <Route path="admin/usage" element={<RequireAuth admin><AdminUsage /></RequireAuth>} />
          </Route>
          {/* The report view uses the full width, so it sits outside the sidebar layout */}
          <Route path="/reports/:reportId" element={<RequireAuth><ReportView /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
