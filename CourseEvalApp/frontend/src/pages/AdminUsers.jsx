import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import PropTypes from 'prop-types';
import { api, formatDate } from '../api';
import { useAuth } from '../auth';

const TABS = [
  { value: 'pending', label: 'Waiting for approval' },
  { value: 'approved', label: 'Active' },
  { value: 'disabled', label: 'Disabled' },
  { value: 'rejected', label: 'Rejected' },
];

const MODES = [
  { value: 'our_key_capped', label: 'Lab credit, yearly limit' },
  { value: 'our_key_unlimited', label: 'Lab credit, no limit' },
  { value: 'own_key', label: 'Own API key' },
];

const PROVIDER_NAMES = { openai: 'OpenAI', anthropic: 'Anthropic', gemini: 'Gemini' };

function CreditEditor({ user, onSaved }) {
  const [mode, setMode] = useState(user.credit_mode);
  const [cap, setCap] = useState(user.yearly_cap_usd ?? 20);
  const dirty = mode !== user.credit_mode || (mode === 'our_key_capped' && Number(cap) !== user.yearly_cap_usd);

  const save = async () => {
    try {
      await api(`/admin/users/${user.id}/credits`, {
        method: 'PATCH', body: { credit_mode: mode, yearly_cap_usd: mode === 'our_key_capped' ? Number(cap) : null },
      });
      toast.success(`Credit plan updated for ${user.name}`);
      onSaved();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <select className="input h-8 w-44" value={mode} onChange={(e) => setMode(e.target.value)}>
        {MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
      </select>
      {mode === 'our_key_capped' && (
        <div className="flex items-center gap-1 text-sm">
          <span className="text-ink-muted">$</span>
          <input className="input h-8 w-20 tabular-nums" type="number" min="0" step="1" value={cap} onChange={(e) => setCap(e.target.value)} />
          <span className="text-ink-muted">/yr</span>
        </div>
      )}
      {dirty && <button className="btn-secondary py-1" onClick={save}>Save</button>}
      {mode === 'own_key' && !dirty && (
        <span className="text-xs text-ink-muted">{user.has_own_key ? `${PROVIDER_NAMES[user.api_provider] || 'Key'} key saved` : 'No key yet'}</span>
      )}
    </div>
  );
}

CreditEditor.propTypes = {
  user: PropTypes.shape({
    id: PropTypes.number, name: PropTypes.string, credit_mode: PropTypes.string, yearly_cap_usd: PropTypes.number,
    has_own_key: PropTypes.bool, api_provider: PropTypes.string,
  }).isRequired,
  onSaved: PropTypes.func.isRequired,
};

export default function AdminUsers() {
  const { user: me } = useAuth();
  const [tab, setTab] = useState('pending');
  const [users, setUsers] = useState(null);
  const [summary, setSummary] = useState({});

  const load = () => {
    api(`/admin/users?status=${tab}`).then(setUsers).catch((err) => toast.error(err.message));
    api('/admin/summary').then(setSummary).catch(() => {});
  };
  useEffect(load, [tab]);

  const act = async (user, action) => {
    const verbs = { approve: 'Approve', reject: 'Reject', disable: 'Disable', enable: 'Enable' };
    if (action !== 'approve' && !window.confirm(`${verbs[action]} ${user.name} (${user.email})?`)) return;
    try {
      await api(`/admin/users/${user.id}/${action}`, { method: 'POST' });
      toast.success(`${verbs[action]}d ${user.name}`);
      load();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <div className="page max-w-6xl">
      <h1 className="page-title">Users</h1>
      <p className="page-subtitle">Approve new professors and set how each one pays for analyses. Report contents stay private to their owners.</p>

      <div className="mt-6 flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm ${tab === t.value ? 'border-accent font-medium text-ink' : 'border-transparent text-ink-muted hover:text-ink'}`}
          >
            {t.label}{summary[t.value] ? <span className="ml-2 rounded bg-line-soft px-1.5 text-xs tabular-nums">{summary[t.value]}</span> : null}
          </button>
        ))}
      </div>

      {users === null && <p className="mt-6 text-sm text-ink-muted">Loading…</p>}
      {users?.length === 0 && <p className="mt-6 text-sm text-ink-muted">No accounts here.</p>}

      {users?.length > 0 && (
        <div className="card mt-4 overflow-x-auto p-0">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Registered</th>
                {tab === 'approved' && <th>Credit plan</th>}
                {tab === 'approved' && <th className="text-right">Reports</th>}
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <p className="font-medium text-ink">{u.name}{u.role === 'admin' && <span className="badge ml-2 bg-line-soft text-ink-soft">admin</span>}</p>
                    <p className="text-xs text-ink-muted">{u.email}</p>
                    {u.department && <p className="text-xs text-ink-muted">{u.department}</p>}
                  </td>
                  <td className="text-ink-soft">{formatDate(u.created_at)}</td>
                  {tab === 'approved' && <td><CreditEditor key={`${u.id}-${u.credit_mode}-${u.yearly_cap_usd}`} user={u} onSaved={load} /></td>}
                  {tab === 'approved' && <td className="text-right tabular-nums">{u.report_count ?? 0}</td>}
                  <td className="space-x-2 whitespace-nowrap text-right">
                    {tab === 'pending' && (
                      <>
                        <button className="btn-primary py-1" onClick={() => act(u, 'approve')}>Approve</button>
                        <button className="btn-danger py-1" onClick={() => act(u, 'reject')}>Reject</button>
                      </>
                    )}
                    {tab === 'approved' && u.id !== me.id && <button className="btn-danger py-1" onClick={() => act(u, 'disable')}>Disable</button>}
                    {tab === 'disabled' && <button className="btn-secondary py-1" onClick={() => act(u, 'enable')}>Enable</button>}
                    {tab === 'rejected' && <button className="btn-secondary py-1" onClick={() => act(u, 'approve')}>Approve</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
