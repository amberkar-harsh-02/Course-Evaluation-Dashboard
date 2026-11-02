import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { api, formatMoney } from '../api';

const MODE_LABELS = { our_key_capped: 'Lab credit, limit', our_key_unlimited: 'Lab credit, no limit', own_key: 'Own key' };

export default function AdminUsage() {
  const [usage, setUsage] = useState(null);

  useEffect(() => { api('/admin/usage').then(setUsage).catch((err) => toast.error(err.message)); }, []);

  if (!usage) return <div className="page text-sm text-ink-muted">Loading…</div>;

  return (
    <div className="page max-w-5xl">
      <h1 className="page-title">Usage and credits</h1>
      <p className="page-subtitle">Spending on the lab&apos;s OpenAI credit since {usage.credit_year_start}. Runs on professors&apos; own keys cost the lab nothing.</p>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <div className="card">
          <p className="text-sm text-ink-muted">Spent this credit year</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">{formatMoney(usage.lab_spend_usd)}</p>
        </div>
        <div className="card">
          <p className="text-sm text-ink-muted">Total budget</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">{usage.budget_usd ? formatMoney(usage.budget_usd) : 'Not set'}</p>
        </div>
        <div className="card">
          <p className="text-sm text-ink-muted">Budget left</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">{usage.budget_remaining_usd != null ? formatMoney(usage.budget_remaining_usd) : '—'}</p>
        </div>
      </div>

      <div className="card mt-6 overflow-x-auto p-0">
        <table className="table">
          <thead>
            <tr>
              <th>Professor</th>
              <th>Plan</th>
              <th className="text-right">Runs</th>
              <th className="text-right">Tokens (in / out)</th>
              <th className="text-right">Lab cost</th>
              <th className="text-right">Yearly limit</th>
            </tr>
          </thead>
          <tbody>
            {usage.per_user.length === 0 && (
              <tr><td colSpan={6} className="text-center text-ink-muted">No analyses yet this credit year.</td></tr>
            )}
            {usage.per_user.map((row) => (
              <tr key={row.user_id}>
                <td>{row.email}</td>
                <td className="text-ink-soft">{MODE_LABELS[row.credit_mode] || row.credit_mode}</td>
                <td className="text-right tabular-nums">{row.runs}</td>
                <td className="text-right tabular-nums text-ink-soft">{row.input_tokens.toLocaleString()} / {row.output_tokens.toLocaleString()}</td>
                <td className="text-right font-medium tabular-nums">{formatMoney(row.lab_cost_usd)}</td>
                <td className="text-right tabular-nums text-ink-soft">{row.credit_mode === 'our_key_capped' ? formatMoney(row.yearly_cap_usd) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
