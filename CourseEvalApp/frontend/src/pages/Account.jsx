import { useEffect, useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import { api, formatMoney, setToken } from '../api';
import { useAuth } from '../auth';

const MODE_LABELS = {
  our_key_capped: 'Lab AI credit with a yearly limit',
  our_key_unlimited: 'Lab AI credit, no personal limit',
  own_key: 'Your own API key',
};

const KEY_HELP = {
  openai: { placeholder: 'sk-…', url: 'https://platform.openai.com/api-keys' },
  anthropic: { placeholder: 'sk-ant-…', url: 'https://console.anthropic.com/settings/keys' },
  gemini: { placeholder: 'AIza…', url: 'https://aistudio.google.com/apikey' },
};

const defaultModelOf = (provider) => provider?.models.find((m) => m.default)?.model_id || provider?.models[0]?.model_id || '';

export default function Account() {
  const { user } = useAuth();
  const [credits, setCredits] = useState(null);
  const [newKey, setNewKey] = useState('');
  const [catalog, setCatalog] = useState([]);
  const [provider, setProvider] = useState('openai');
  const [model, setModel] = useState('');
  const [savedModel, setSavedModel] = useState('');
  const [passwords, setPasswords] = useState({ current: '', next: '', confirm: '' });

  useEffect(() => { api('/me/credits').then(setCredits).catch((err) => toast.error(err.message)); }, []);
  useEffect(() => {
    api('/models').then((list) => {
      setCatalog(list);
      setModel((current) => current || defaultModelOf(list[0]));
    }).catch((err) => toast.error(err.message));
  }, []);
  // Start the form on the saved provider, and keep the "change model" picker on the saved model
  useEffect(() => {
    if (credits?.api_provider) {
      setProvider(credits.api_provider);
      setModel(credits.api_model);
      setSavedModel(credits.api_model);
    }
  }, [credits?.api_provider, credits?.api_model]);

  const providerInfo = useMemo(() => catalog.find((p) => p.provider === provider), [catalog, provider]);
  const savedProviderInfo = useMemo(() => catalog.find((p) => p.provider === credits?.api_provider), [catalog, credits?.api_provider]);
  const pickProvider = (value) => {
    setProvider(value);
    setModel(defaultModelOf(catalog.find((p) => p.provider === value)));
  };

  const saveKey = async (event) => {
    event.preventDefault();
    try {
      setCredits(await api('/me/api-key', { method: 'PUT', body: { provider, model, api_key: newKey.trim() } }));
      setNewKey('');
      toast.success('Key saved');
    } catch (err) {
      toast.error(err.message);
    }
  };

  const changeModel = async () => {
    try {
      setCredits(await api('/me/api-model', { method: 'PUT', body: { provider: credits.api_provider, model: savedModel } }));
      toast.success('Model changed');
    } catch (err) {
      toast.error(err.message);
    }
  };

  const removeKey = async () => {
    if (!window.confirm(`Remove your saved ${credits?.api_provider_name || ''} key?`)) return;
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
        <p className="page-subtitle">Signed in as {user?.name} ({user?.email})</p>
      </div>

      <section className="card">
        <h2 className="font-serif text-lg font-medium text-ink">AI credit</h2>
        {credits ? (
          <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-ink-muted">Plan</dt>
              <dd className="mt-1 font-medium">{MODE_LABELS[credits.credit_mode]}</dd>
            </div>
            <div>
              <dt className="text-ink-muted">Used since {credits.credit_year_start}</dt>
              <dd className="mt-1 font-medium tabular-nums">{formatMoney(credits.spent_this_year_usd)}</dd>
            </div>
            {credits.credit_mode === 'our_key_capped' && (
              <div>
                <dt className="text-ink-muted">Left this year</dt>
                <dd className="mt-1 font-medium tabular-nums">{formatMoney(credits.remaining_usd)} of {formatMoney(credits.yearly_cap_usd)}</dd>
              </div>
            )}
          </dl>
        ) : <p className="mt-2 text-sm text-ink-muted">Loading…</p>}
        <p className="mt-4 text-xs text-ink-muted">The plan is set by the administrator. Contact them if you need more credit.</p>
      </section>

      <section className="card">
        <h2 className="font-serif text-lg font-medium text-ink">Your own AI key</h2>
        <p className="mt-1 max-w-[68ch] text-sm text-ink-soft">
          Used only when your plan is &ldquo;your own API key&rdquo;. Choose the AI provider and model, then paste a key
          from that provider. The key is stored encrypted and never shown again; only its last four characters are displayed.
        </p>

        {credits?.has_own_key && (
          <div className="mt-4 rounded-md border border-line">
            <dl className="grid gap-4 px-4 py-3 text-sm sm:grid-cols-3">
              <div><dt className="text-xs text-ink-muted">Provider</dt><dd className="mt-0.5 font-medium">{credits.api_provider_name}</dd></div>
              <div><dt className="text-xs text-ink-muted">Model</dt><dd className="mt-0.5 font-medium">{credits.api_model_label}</dd></div>
              <div><dt className="text-xs text-ink-muted">Key ending in</dt><dd className="mt-0.5 font-mono font-medium">{credits.api_key_last4}</dd></div>
            </dl>
            <div className="flex flex-wrap items-end gap-3 border-t border-line-soft px-4 py-3">
              {savedProviderInfo && savedProviderInfo.models.length > 1 && (
                <>
                  <div className="min-w-56 flex-1">
                    <label className="label" htmlFor="saved-model">Change model</label>
                    <select id="saved-model" className="input" value={savedModel} onChange={(e) => setSavedModel(e.target.value)}>
                      {savedProviderInfo.models.map((m) => <option key={m.model_id} value={m.model_id}>{m.label}</option>)}
                    </select>
                  </div>
                  <button type="button" className="btn-secondary" onClick={changeModel} disabled={savedModel === credits.api_model}>Use this model</button>
                </>
              )}
              <button type="button" className="btn-danger ml-auto" onClick={removeKey}>Remove key</button>
            </div>
          </div>
        )}

        <form onSubmit={saveKey} className="mt-5 space-y-4">
          <p className="text-sm font-medium text-ink">{credits?.has_own_key ? 'Replace with a new key' : 'Add a key'}</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="provider">AI provider</label>
              <select id="provider" className="input" value={provider} onChange={(e) => pickProvider(e.target.value)}>
                {catalog.map((p) => <option key={p.provider} value={p.provider}>{p.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="model">Model</label>
              <select id="model" className="input" value={model} onChange={(e) => setModel(e.target.value)}>
                {providerInfo?.models.map((m) => <option key={m.model_id} value={m.model_id}>{m.label}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="label" htmlFor="api-key">{providerInfo?.name || 'API'} key</label>
            <div className="flex gap-3">
              <input id="api-key" className="input font-mono" type="password" autoComplete="off"
                     placeholder={KEY_HELP[provider]?.placeholder} value={newKey} onChange={(e) => setNewKey(e.target.value)} />
              <button className="btn-secondary shrink-0" disabled={!newKey.trim() || !model}>Save key</button>
            </div>
            {KEY_HELP[provider] && (
              <p className="mt-1 text-xs text-ink-muted">
                Create a key on the <a className="link" href={KEY_HELP[provider].url} target="_blank" rel="noopener noreferrer">{providerInfo?.name} key page</a>.
                Usage is billed to your own account with that provider.
              </p>
            )}
          </div>
          <p className="notice-info text-xs">
            The analysis was tested most with OpenAI&apos;s GPT models. Other providers and models may score some comments differently.
          </p>
        </form>
      </section>

      <section className="card">
        <h2 className="font-serif text-lg font-medium text-ink">Change password</h2>
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
