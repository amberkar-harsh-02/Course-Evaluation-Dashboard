import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import AuthShell from '../components/AuthShell';

export default function Register() {
  const [form, setForm] = useState({ name: '', email: '', department: '', password: '', confirm: '' });
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value });

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    if (form.password !== form.confirm) { setError('The passwords do not match.'); return; }
    setBusy(true);
    try {
      await api('/auth/register', {
        method: 'POST',
        body: { name: form.name, email: form.email, department: form.department || null, password: form.password },
      });
      setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <AuthShell title="Request received">
        <p className="notice-success">
          Thanks. An administrator will review your request. You can sign in once it is approved.
        </p>
        <Link to="/login" className="btn-secondary mt-6 w-full">Back to sign in</Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Request access" subtitle="Accounts are activated after an administrator approves them.">
      <form onSubmit={submit} className="space-y-4">
        {error && <p className="notice-error">{error}</p>}
        <div>
          <label className="label" htmlFor="name">Full name</label>
          <input id="name" className="input" required minLength={2} value={form.name} onChange={update('name')} />
        </div>
        <div>
          <label className="label" htmlFor="email">Institutional email</label>
          <input id="email" className="input" type="email" required value={form.email} onChange={update('email')} />
        </div>
        <div>
          <label className="label" htmlFor="department">Department <span className="font-normal text-slate-400">(optional)</span></label>
          <input id="department" className="input" value={form.department} onChange={update('department')} />
        </div>
        <div>
          <label className="label" htmlFor="password">Password</label>
          <input id="password" className="input" type="password" autoComplete="new-password" required minLength={10} value={form.password} onChange={update('password')} />
          <p className="mt-1 text-xs text-slate-500">At least 10 characters, mixing letters with numbers or symbols.</p>
        </div>
        <div>
          <label className="label" htmlFor="confirm">Repeat password</label>
          <input id="confirm" className="input" type="password" autoComplete="new-password" required value={form.confirm} onChange={update('confirm')} />
        </div>
        <button className="btn-primary w-full" disabled={busy}>{busy ? 'Sending…' : 'Request access'}</button>
      </form>
      <p className="mt-6 text-sm text-slate-600">
        Already approved? <Link to="/login" className="font-medium text-blue-800 hover:underline">Sign in</Link>
      </p>
    </AuthShell>
  );
}
