import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, formatMoney } from '../api';
import { useAuth } from '../auth';

const ACCEPTED = '.pdf,.docx,.xlsx,.xls,.csv';
const STAGES = {
  extracting: 'Reading the file and finding student comments',
  comments: 'Analyzing comments',
  summaries: 'Writing topic summaries',
  done: 'Finished',
};

export default function NewAnalysis() {
  const { isAdmin } = useAuth();
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [course, setCourse] = useState('');
  const [term, setTerm] = useState('');
  const [model, setModel] = useState('openai');
  const [credits, setCredits] = useState(null);
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);

  useEffect(() => { api('/me/credits').then(setCredits).catch(() => {}); }, []);

  // Poll the running job until it finishes
  useEffect(() => {
    if (!job || ['complete', 'failed'].includes(job.status)) return undefined;
    const timer = setTimeout(async () => {
      try {
        setJob(await api(`/analyses/${job.job_id}`));
      } catch (err) {
        setError(err.message);
      }
    }, 1500);
    return () => clearTimeout(timer);
  }, [job]);

  useEffect(() => {
    if (job?.status === 'complete' && job.report_id) navigate(`/reports/${job.report_id}`);
  }, [job, navigate]);

  const pick = (picked) => {
    if (!picked) return;
    setFile(picked);
    if (!course) setCourse(picked.name.replace(/\.[^.]+$/, ''));
  };

  const start = async (event) => {
    event.preventDefault();
    if (!file) return;
    setError('');
    const form = new FormData();
    form.append('file', file);
    form.append('model_choice', model);
    if (course) form.append('course', course);
    if (term) form.append('term', term);
    try {
      const { job_id: jobId } = await api('/analyses', { method: 'POST', form });
      setJob({ job_id: jobId, status: 'queued', done: 0, total: 0 });
    } catch (err) {
      setError(err.message);
    }
  };

  const running = job && !['complete', 'failed'].includes(job.status);
  const percent = job?.total ? Math.round((job.done / job.total) * 100) : null;

  return (
    <div className="page max-w-3xl">
      <h1 className="page-title">New analysis</h1>
      <p className="page-subtitle">Upload one course evaluation export. The comments are read, sorted into teaching topics and scored.</p>

      {credits && (
        <div className="notice-info mt-6">
          {credits.credit_mode === 'own_key' && <>This analysis will use <strong>your own OpenAI key</strong>{credits.api_key_last4 ? ` (ending ${credits.api_key_last4})` : ''}.</>}
          {credits.credit_mode === 'our_key_unlimited' && <>This analysis uses the lab&apos;s AI credit.</>}
          {credits.credit_mode === 'our_key_capped' && (
            <>AI credit left this year: <strong>{formatMoney(credits.remaining_usd)}</strong> of {formatMoney(credits.yearly_cap_usd)}. A typical file uses a few cents to about a dollar.</>
          )}
        </div>
      )}

      <form onSubmit={start} className="card mt-6 space-y-5">
        {error && <p className="notice-error">{error}</p>}

        <div
          role="button"
          tabIndex={0}
          onClick={() => !running && inputRef.current?.click()}
          onKeyDown={(e) => { if (e.key === 'Enter' && !running) inputRef.current?.click(); }}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); if (!running) pick(e.dataTransfer.files?.[0]); }}
          className={`rounded border-2 border-dashed px-6 py-10 text-center text-sm ${dragging ? 'border-accent bg-accent-tint' : 'border-line bg-page'} ${running ? 'opacity-60' : 'cursor-pointer hover:border-ink-muted'}`}
        >
          {file ? (
            <p><span className="font-medium text-ink">{file.name}</span> <span className="text-ink-muted">({(file.size / 1024 / 1024).toFixed(1)} MB)</span></p>
          ) : (
            <p className="text-ink-soft">Drop a file here or <span className="font-medium text-accent">choose one</span><br /><span className="text-xs text-ink-muted">PDF, Word, Excel or CSV, up to 25 MB</span></p>
          )}
          <input ref={inputRef} type="file" accept={ACCEPTED} className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="course">Course</label>
            <input id="course" className="input" value={course} onChange={(e) => setCourse(e.target.value)} placeholder="e.g. CHEM 110" disabled={running} />
          </div>
          <div>
            <label className="label" htmlFor="term">Term <span className="font-normal text-ink-muted">(optional)</span></label>
            <input id="term" className="input" value={term} onChange={(e) => setTerm(e.target.value)} placeholder="e.g. Fall 2025" disabled={running} />
          </div>
        </div>

        {isAdmin && (
          <div>
            <label className="label" htmlFor="model">Model</label>
            <select id="model" className="input" value={model} onChange={(e) => setModel(e.target.value)} disabled={running}>
              <option value="openai">OpenAI (lab credit)</option>
              <option value="local">Local model on the lab Mac Studio (campus network only)</option>
            </select>
          </div>
        )}

        <div className="flex items-center gap-3">
          <button className="btn-primary" disabled={!file || running}>{running ? 'Analyzing…' : 'Start analysis'}</button>
          {credits?.credit_mode === 'own_key' && !credits.has_own_key && (
            <Link to="/account" className="text-sm text-accent hover:underline">Add your OpenAI key first</Link>
          )}
        </div>
      </form>

      {job && (
        <div className="card mt-6">
          {job.status === 'failed' ? (
            <p className="notice-error">{job.error}</p>
          ) : (
            <>
              <p className="text-sm font-medium text-ink">{STAGES[job.stage] || 'Waiting to start'}</p>
              <div className="mt-3 h-2 w-full overflow-hidden rounded bg-line-soft">
                <div className="h-2 bg-accent transition-all" style={{ width: `${percent ?? 5}%` }} />
              </div>
              <p className="mt-2 text-xs text-ink-muted">
                {job.total ? `${job.done} of ${job.total}` : 'This usually takes under a minute.'} You can leave this page; the report will appear under My reports.
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
