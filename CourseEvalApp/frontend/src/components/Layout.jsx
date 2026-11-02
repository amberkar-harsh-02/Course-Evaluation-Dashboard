import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';
import { ThemeToggle } from '../theme';

const linkClass = ({ isActive }) =>
  `block rounded px-3 py-2 text-sm ${isActive ? 'bg-line-soft font-medium text-ink' : 'text-ink-soft hover:bg-page hover:text-ink'}`;

function Navigation() {
  const { user, isAdmin, signOut } = useAuth();
  const navigate = useNavigate();
  return (
    <>
      <nav className="flex-1 space-y-1 p-3" aria-label="Main">
        <NavLink to="/" end className={linkClass}>My reports</NavLink>
        <NavLink to="/new" className={linkClass}>New analysis</NavLink>
        <NavLink to="/account" className={linkClass}>Account</NavLink>
        {isAdmin && (
          <>
            <p className="px-3 pb-1 pt-6 text-xs font-medium text-ink-muted">Administration</p>
            <NavLink to="/admin/users" className={linkClass}>Users</NavLink>
            <NavLink to="/admin/usage" className={linkClass}>Usage and credits</NavLink>
          </>
        )}
      </nav>
      <div className="border-t border-line p-4 text-sm">
        <p className="truncate font-medium text-ink">{user?.name}</p>
        <p className="truncate text-xs text-ink-muted">{user?.email}</p>
        <div className="mt-3 flex items-center justify-between gap-3">
          <button
            className="text-xs font-medium text-ink-soft underline-offset-2 hover:underline"
            onClick={() => { signOut(); navigate('/login'); }}
          >
            Sign out
          </button>
          <ThemeToggle />
        </div>
      </div>
    </>
  );
}

export default function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  useEffect(() => { setMenuOpen(false); }, [location.pathname]);

  return (
    <div className="min-h-screen md:flex">
      {/* Phones and small tablets: top bar with a menu */}
      <header className="sticky top-0 z-20 border-b border-line bg-paper md:hidden">
        <div className="flex items-center justify-between px-5 py-3">
          <p className="font-serif text-lg text-ink">Course Evaluation</p>
          <button className="btn-secondary px-3 py-1.5" aria-expanded={menuOpen} aria-controls="mobile-menu" onClick={() => setMenuOpen(!menuOpen)}>
            {menuOpen ? 'Close' : 'Menu'}
          </button>
        </div>
        {menuOpen && <div id="mobile-menu" className="border-t border-line"><Navigation /></div>}
      </header>

      <aside className="hidden w-60 shrink-0 flex-col border-r border-line bg-paper md:sticky md:top-0 md:flex md:h-screen">
        <div className="border-b border-line px-5 py-5">
          <p className="font-serif text-lg text-ink">Course Evaluation</p>
          <p className="text-xs text-ink-muted">Analysis of student feedback</p>
        </div>
        <Navigation />
      </aside>
      <main className="min-w-0 flex-1">
        <Outlet />
      </main>
    </div>
  );
}
