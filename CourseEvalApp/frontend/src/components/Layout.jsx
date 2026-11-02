import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';

const linkClass = ({ isActive }) =>
  `block rounded-md px-3 py-2 text-sm ${isActive ? 'bg-slate-100 font-medium text-slate-900' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'}`;

export default function Layout() {
  const { user, isAdmin, signOut } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-5">
          <p className="text-base font-semibold text-slate-900">Course Evaluation</p>
          <p className="text-xs text-slate-500">Analysis of student feedback</p>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          <NavLink to="/" end className={linkClass}>My reports</NavLink>
          <NavLink to="/new" className={linkClass}>New analysis</NavLink>
          <NavLink to="/account" className={linkClass}>Account</NavLink>
          {isAdmin && (
            <>
              <p className="px-3 pb-1 pt-5 text-xs font-semibold uppercase tracking-wide text-slate-400">Administration</p>
              <NavLink to="/admin/users" className={linkClass}>Users</NavLink>
              <NavLink to="/admin/usage" className={linkClass}>Usage and credits</NavLink>
            </>
          )}
        </nav>
        <div className="border-t border-slate-200 p-4 text-sm">
          <p className="truncate font-medium text-slate-800">{user?.name}</p>
          <p className="truncate text-xs text-slate-500">{user?.email}</p>
          <button
            className="mt-3 text-xs font-medium text-slate-600 underline-offset-2 hover:underline"
            onClick={() => { signOut(); navigate('/login'); }}
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
