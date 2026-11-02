import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { api, formatMoney, setToken } from '../api';
import { useAuth } from '../auth';

const MODE_LABELS = {
  our_key_capped: 'Lab AI credit with a yearly limit',
  our_key_unlimited: 'Lab AI credit, no personal limit',
  own_key: 'Your own OpenAI key',
};

export default function Account() {
  const { user } = useAuth();
  const [credits, setCredits] = useState(null);
  const [newKey, setNewKey] = useState('');
  const [passwords, setPasswords] = useState({ current: '', next: '', confirm: '' });

  useEffect(() => { api('/me/credits').then(setCredits).catch((err) => toast.error(err.message)); }, []);

  const saveKey = async (event) => {
    event.preventDefault();
    try {
      setCredits(await api('/me/api-key', { method: 'PUT', body: { api_key: newKey.trim() } }));
      setNewKey('');
      toast.success('Key saved');
    } catch (err) {
      toast.error(err.message);
    }
  };

  const removeKey = async () => {
    if (!window.confirm('Remove your saved OpenAI key?')) return;
    try {
      setCredits(await api('/me/api-key', { method: 'DELETE' }));
      toast.success('Key removed');
    } catch (err) {
      toast.error(err.message);
    }
  };

  const changePassword = async (event) => {
    event.preventDefault();
    if (passwords.next !== passwords.confirm) { toast.error('The new passwords do not match.'); return; }
    try {
      const result = await api('/auth/change-password', {
        method: 'POST', body: { current_password: passwords.current, new_password: passwords.next },
      });
      setToken(result.access_token);
      setPasswords({ current: '', next: '', confirm: '' });
      toast.success('Password changed. Other devices were signed out.');
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <div className="page max-w-3xl space-y-6">
      <div>
        <h1 className="page-title">Account</h1>
        <p className="page-subtitle">{user?.name} · {user?.email}</p>
      </div>

      <section className="card">
        <h2 className="text-base font-semibold text-slate-900">AI credit</h2>
        {credits ? (
          <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-slate-500">Plan</dt>
              <dd className="mt-1 font-medium">{MODE_LABELS[credits.credit_mode]}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Used since {credits.credit_year_start}</dt>
              <dd className="mt-1 font-medium tabular-nums">{formatMoney(credits.spent_this_year_usd)}</dd>
            </div>
            {credits.credit_mode === 'our_key_capped' && (
              <div>
                <dt className="text-slate-500">Left this year</dt>
                <dd className="mt-1 font-medium tabular-nums">{formatMoney(credits.remaining_usd)} of {formatMoney(credits.yearly_cap_usd)}</dd>
              </div>
            )}
          </dl>
        ) : <p className="mt-2 text-sm text-slate-500">Loading…</p>}
        <p className="mt-4 text-xs text-slate-500">The plan is set by the administrator. Contact them if you need more credit.</p>
      </section>

      <section className="card">
        <h2 className="text-base font-semibold text-slate-900">Your own OpenAI key</h2>
        <p className="mt-1 text-sm text-slate-600">
          Used only when your plan is &ldquo;your own OpenAI key&rdquo;. It is stored encrypted and is never shown again;
          only its last four characters are displayed.
        </p>
        {credits?.has_own_key ? (
          <div className="mt-4 flex items-center justify-between rounded-md border border-slate-200 px-4 py-3 text-sm">
            <span>Saved key ending in <strong className="font-mono">{credits.api_key_last4}</strong></span>
            <button className="btn-danger" onClick={removeKey}>Remove</button>
          </div>
        ) : null}
        <form onSubmit={saveKey} className="mt-4 flex gap-3">
          <input className="input font-mono" type="password" autoComplete="off" placeholder="sk-…" value={newKey} onChange={(e) => setNewKey(e.target.value)} />
          <button className="btn-secondary shrink-0" disabled={!newKey.trim()}>{credits?.has_own_key ? 'Replace key' : 'Save key'}</button>
        </form>
      </section>

      <section className="card">
        <h2 className="text-base font-semibold text-slate-900">Change password</h2>
        <form onSubmit={changePassword} className="mt-4 grid gap-4 sm:grid-cols-3">
          <input className="input" type="password" autoComplete="current-password" placeholder="Current password" required value={passwords.current} onChange={(e) => setPasswords({ ...passwords, current: e.target.value })} />
          <input className="input" type="password" autoComplete="new-password" placeholder="New password" required minLength={10} value={passwords.next} onChange={(e) => setPasswords({ ...passwords, next: e.target.value })} />
          <input className="input" type="password" autoComplete="new-password" placeholder="Repeat new password" required value={passwords.confirm} onChange={(e) => setPasswords({ ...passwords, confirm: e.target.value })} />
          <div className="sm:col-span-3"><button className="btn-secondary">Change password</button></div>
        </form>
      </section>
    </div>
  );
}
