import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';
import { ThemeToggle } from '../theme';
import { useReportNav } from '../reportNav';
import { formatScore, scoreTone, shortName } from '../report/model';

const linkClass = ({ isActive }) =>
  `block rounded-md px-3 py-2 text-sm transition-colors duration-150 ${isActive ? 'bg-line-soft font-medium text-ink' : 'text-ink-soft hover:bg-page hover:text-ink'}`;

const TONE_TEXT = { low: 'text-score-low', mid: 'text-score-mid', high: 'text-score-high', none: 'text-ink-muted' };

/** The open report under "My reports", with its topics nested below, like the original portal. */
function ReportTree() {
  const { openReport } = useReportNav();
  const location = useLocation();
  const [expanded, setExpanded] = useState(true);
  if (!openReport) return null;

  const base = `/reports/${openReport.id}`;
  const onReport = location.pathname === base;
  const activeTopic = onReport ? new URLSearchParams(location.search).get('topic') : null;
  const itemClass = (active) =>
    `flex items-center justify-between gap-2 rounded-md px-2 py-1.5 text-sm transition-colors duration-150 ${
      active ? 'bg-accent-tint font-medium text-accent' : 'text-ink-soft hover:bg-page hover:text-ink'}`;

  return (
    <div className="animate-fade-in pb-1 pt-1">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        aria-controls="report-tree"
        className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-left text-sm font-medium text-ink transition-colors hover:bg-page"
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
             className={`h-3.5 w-3.5 shrink-0 text-ink-muted transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}>
          <path d="m6 4 4 4-4 4" />
        </svg>
        <span className="min-w-0 truncate" title={`${openReport.course}${openReport.term ? ` (${openReport.term})` : ''}`}>
          {openReport.course}{openReport.term && <span className="font-normal text-ink-muted"> ({openReport.term})</span>}
        </span>
      </button>
      {/* grid-rows 0fr -> 1fr animates the height without measuring it */}
      <div id="report-tree" className={`grid transition-[grid-template-rows] duration-200 ease-out ${expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}`}>
        <ul className="ml-[1.2rem] min-h-0 space-y-0.5 overflow-hidden border-l border-line pl-2" aria-label="Topics in this report">
          <li className="pt-1">
            <Link to={base} className={itemClass(onReport && !activeTopic)} aria-current={onReport && !activeTopic ? 'page' : undefined}>
              Overview
            </Link>
          </li>
          {openReport.topics.map((t) => {
            const active = activeTopic === t.topic;
            return (
              <li key={t.topic}>
                <Link to={`${base}?topic=${encodeURIComponent(t.topic)}`} className={itemClass(active)} title={t.topic} aria-current={active ? 'page' : undefined}>
                  <span className="truncate">{shortName(t.topic)}</span>
                  <span className={`num shrink-0 text-xs ${TONE_TEXT[scoreTone(t.average)]}`}>{formatScore(t.average, 1)}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

function Navigation() {
  const { user, isAdmin, signOut } = useAuth();
  const navigate = useNavigate();
  return (
    <>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="Main">
        <NavLink to="/" end className={linkClass}>My reports</NavLink>
        <ReportTree />
        <NavLink to="/new" className={linkClass}>New analysis</NavLink>
        <NavLink to="/guide" className={linkClass}>Guide</NavLink>
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
  useEffect(() => { setMenuOpen(false); }, [location.pathname, location.search]);

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
        {menuOpen && <div id="mobile-menu" className="max-h-[80vh] animate-fade-in overflow-y-auto border-t border-line"><Navigation /></div>}
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
