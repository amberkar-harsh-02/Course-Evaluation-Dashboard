import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import PropTypes from 'prop-types';
import { api, formatMoney } from '../api';
import { useAuth } from '../auth';

const FORMATS = [
  { label: 'PDF', ext: ['pdf'] },
  { label: 'Word', ext: ['docx'] },
  { label: 'Excel', ext: ['xlsx', 'xls'] },
  { label: 'CSV', ext: ['csv'] },
];
const ACCEPTED = FORMATS.flatMap((f) => f.ext.map((e) => `.${e}`)).join(',');
const MAX_MB = 25;
const STEPS = [
  { key: 'extracting', label: 'Reading the file', detail: 'Finding the student comments' },
  { key: 'comments', label: 'Analyzing comments', detail: 'Sorting each comment into teaching topics and scoring it' },
  { key: 'summaries', label: 'Writing summaries', detail: 'Summarizing what students said about each topic' },
];

const extensionOf = (name) => (name.includes('.') ? name.split('.').pop().toLowerCase() : '');
const formatOf = (name) => FORMATS.find((f) => f.ext.includes(extensionOf(name)));
const sizeText = (bytes) => (bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`);

function checkFile(file) {
  if (!formatOf(file.name)) {
    const ext = extensionOf(file.name);
    return `${ext ? `This is a .${ext} file.` : 'This file has no type.'} Upload a PDF, Word, Excel or CSV file.`;
  }
  if (file.size > MAX_MB * 1024 * 1024) return `This file is ${sizeText(file.size)}. Files can be up to ${MAX_MB} MB.`;
  if (file.size === 0) return 'This file is empty. Choose the exported evaluation file.';
  return '';
}

function UploadIcon({ className }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M9 22H8a5 5 0 0 1-.6-9.96A7 7 0 0 1 21 10.5h.5a5.5 5.5 0 0 1 1 10.9" />
      <path d="M16 26V15m0 0-4 4m4-4 4 4" />
    </svg>
  );
}

UploadIcon.propTypes = { className: PropTypes.string };

/** Empty drop zone, or the chosen file with Replace and Remove. */
function DropZone({ file, onPick, onRemove, disabled, invalid }) {
  const inputRef = useRef(null);
  const depth = useRef(0); // counts dragenter/dragleave so moving over child elements does not flicker
  const [dragging, setDragging] = useState(false);
  const open = () => { if (!disabled) inputRef.current?.click(); };

  const dragHandlers = {
    onDragEnter: (e) => { e.preventDefault(); if (disabled) return; depth.current += 1; setDragging(true); },
    onDragOver: (e) => { e.preventDefault(); },
    onDragLeave: (e) => { e.preventDefault(); depth.current = Math.max(0, depth.current - 1); if (depth.current === 0) setDragging(false); },
    onDrop: (e) => {
      e.preventDefault();
      depth.current = 0;
      setDragging(false);
      if (!disabled && e.dataTransfer.files?.[0]) onPick(e.dataTransfer.files[0]);
    },
  };

  const input = (
    <input ref={inputRef} type="file" accept={ACCEPTED} className="hidden"
           onChange={(e) => { if (e.target.files?.[0]) onPick(e.target.files[0]); e.target.value = ''; }} />
  );

  if (file) {
    const format = formatOf(file.name);
    return (
      <div {...dragHandlers}
           className={`flex animate-scale-in items-center gap-4 rounded-md border px-4 py-4 transition-colors duration-150 ${dragging ? 'border-accent bg-accent-tint' : 'border-line bg-page'}`}>
        <span className="flex h-12 w-11 shrink-0 items-center justify-center rounded border border-line bg-paper text-[0.65rem] font-semibold text-accent">
          {extensionOf(file.name).toUpperCase()}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-ink" title={file.name}>{file.name}</p>
          <p className="text-sm text-ink-muted">{format?.label} file, {sizeText(file.size)}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button type="button" className="btn-secondary px-3 py-1.5" onClick={open} disabled={disabled}>Replace</button>
          <button type="button" className="btn-secondary px-3 py-1.5" onClick={onRemove} disabled={disabled}>Remove</button>
        </div>
        {input}
      </div>
    );
  }

  return (
    <div
      {...dragHandlers}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label="Choose an evaluation file, or drop one here"
      onClick={open}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } }}
      className={`group relative flex flex-col items-center rounded-md border-2 border-dashed px-6 py-12 text-center transition-[border-color,background-color] duration-200 ${
        dragging ? 'border-accent bg-accent-tint' : invalid ? 'border-score-low/60 bg-page' : 'border-line-strong/70 bg-page hover:border-accent/60'} ${disabled ? 'opacity-60' : 'cursor-pointer'}`}
    >
      <span className={`flex h-14 w-14 items-center justify-center rounded-full bg-paper text-accent shadow-sm ring-1 ring-line transition-transform duration-200 ${dragging ? '-translate-y-1 scale-105' : 'group-hover:-translate-y-0.5'}`}>
        <UploadIcon className="h-7 w-7" />
      </span>
      {/* Phones cannot drag files, so small screens only offer choosing one */}
      <p className="mt-4 font-serif text-lg text-ink">
        {dragging ? 'Drop to upload' : <><span className="sm:hidden">Choose your evaluation file</span><span className="hidden sm:inline">Drag your evaluation file here</span></>}
      </p>
      <p className="mt-1 hidden text-sm text-ink-muted sm:block">or</p>
      <span className="btn-secondary pointer-events-none mt-3 sm:mt-2">Choose a file</span>
      <div className="mt-5 flex flex-wrap items-center justify-center gap-1.5 text-xs text-ink-muted">
        {FORMATS.map((f) => <span key={f.label} className="rounded-sm border border-line bg-paper px-2 py-0.5 font-medium text-ink-soft">{f.label}</span>)}
        <span className="ml-1">up to {MAX_MB} MB</span>
      </div>
      {input}
    </div>
  );
}

DropZone.propTypes = { invalid: PropTypes.bool, file: PropTypes.object, onPick: PropTypes.func.isRequired, onRemove: PropTypes.func.isRequired, disabled: PropTypes.bool };

/** Three steps of an analysis, each done, running or waiting. */
function Progress({ job }) {
  const current = Math.max(0, STEPS.findIndex((s) => s.key === job.stage));
  const finished = job.status === 'complete';
  const percent = job.total ? Math.round((job.done / job.total) * 100) : null;
  return (
    <div className="card mt-6 animate-fade-up" aria-live="polite">
      <h2 className="section-title">Analyzing {job.fileName}</h2>
      <ol className="mt-5 space-y-4">
        {STEPS.map((step, i) => {
          const state = finished || i < current ? 'done' : i === current ? 'active' : 'waiting';
          return (
            <li key={step.key} className="flex gap-3">
              <span className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium transition-colors duration-300 ${
                state === 'done' ? 'border-score-high bg-score-high text-paper'
                  : state === 'active' ? 'border-accent text-accent' : 'border-line text-ink-muted'}`}>
                {state === 'done' ? (
                  <svg aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5"><path d="m4 8.5 2.5 2.5L12 5.5" /></svg>
                ) : state === 'active' ? (
                  <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
                ) : i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className={`text-sm font-medium ${state === 'waiting' ? 'text-ink-muted' : 'text-ink'}`}>
                  {step.label}
                  <span className="sr-only">{state === 'done' ? ' (done)' : state === 'active' ? ' (in progress)' : ' (waiting)'}</span>
                </p>
                <p className="text-xs text-ink-muted">{step.detail}</p>
                {state === 'active' && step.key === 'comments' && (
                  <div className="mt-2">
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-line-soft">
                      <div className="h-full rounded-full bg-accent transition-[width] duration-500 ease-out" style={{ width: `${percent ?? 4}%` }} />
                    </div>
                    {job.total > 0 && <p className="num mt-1 text-xs text-ink-muted">{job.done} of {job.total} comments</p>}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      <p className="mt-5 text-xs text-ink-muted">You can leave this page. The report will appear under My reports when it is ready.</p>
    </div>
  );
}

Progress.propTypes = { job: PropTypes.object.isRequired };

export default function NewAnalysis() {
  const { isAdmin } = useAuth();
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [fileError, setFileError] = useState('');
  const [course, setCourse] = useState('');
  const [courseFromFile, setCourseFromFile] = useState(true);
  const [term, setTerm] = useState('');
  const [model, setModel] = useState('openai');
  const [credits, setCredits] = useState(null);
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => { api('/me/credits').then(setCredits).catch(() => {}); }, []);

  // Poll the running job until it finishes
  useEffect(() => {
    if (!job || ['complete', 'failed'].includes(job.status)) return undefined;
    const timer = setTimeout(async () => {
      try {
        const next = await api(`/analyses/${job.job_id}`);
        setJob((current) => ({ ...next, fileName: current.fileName }));
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
    const problem = checkFile(picked);
    setFileError(problem);
    if (problem) return;
    setFile(picked);
    // Suggest a course name from the file name until the professor types their own
    if (!course || courseFromFile) { setCourse(picked.name.replace(/\.[^.]+$/, '')); setCourseFromFile(true); }
  };
  const remove = () => {
    setFile(null);
    setFileError('');
    if (courseFromFile) setCourse('');
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
      setJob({ job_id: jobId, status: 'queued', done: 0, total: 0, fileName: file.name });
    } catch (err) {
      setError(err.message);
    }
  };

  const running = Boolean(job) && !['complete', 'failed'].includes(job.status);
  const needsKey = credits?.credit_mode === 'own_key' && !credits.has_own_key;

  return (
    <div className="page max-w-3xl">
      <h1 className="page-title">New analysis</h1>
      <p className="page-subtitle">Upload one course evaluation export. The comments are read, sorted into teaching topics and scored.</p>

      {credits && (
        <div className="notice-info mt-6">
          {credits.credit_mode === 'own_key' && (credits.has_own_key
            ? <>This analysis will use <strong>your own {credits.api_provider_name} key</strong> (ending {credits.api_key_last4}) with <strong>{credits.api_model_label}</strong>.</>
            : <>Your plan uses your own API key. Add one in your account first.</>)}
          {credits.credit_mode === 'our_key_unlimited' && <>This analysis uses the lab&apos;s AI credit.</>}
          {credits.credit_mode === 'our_key_capped' && (
            <>AI credit left this year: <strong>{formatMoney(credits.remaining_usd)}</strong> of {formatMoney(credits.yearly_cap_usd)}. A typical file uses a few cents to about a dollar.</>
          )}
        </div>
      )}

      <form onSubmit={start} className="card mt-6 space-y-6">
        {error && <p className="notice-error animate-fade-in">{error}</p>}

        <div>
          <DropZone file={file} onPick={pick} onRemove={remove} disabled={running} invalid={Boolean(fileError)} />
          {fileError && <p className="mt-2 animate-fade-in text-sm text-score-low" role="alert">{fileError}</p>}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="course">Course</label>
            <input id="course" className="input" value={course} placeholder="e.g. CHEM 110" disabled={running}
                   onChange={(e) => { setCourse(e.target.value); setCourseFromFile(false); }} />
            <p className="mt-1 text-xs text-ink-muted">Shown as the report title.</p>
          </div>
          <div>
            <label className="label" htmlFor="term">Term <span className="font-normal text-ink-muted">(optional)</span></label>
            <input id="term" className="input" value={term} onChange={(e) => setTerm(e.target.value)} placeholder="e.g. Fall 2025" disabled={running} />
            <p className="mt-1 text-xs text-ink-muted">Used to line up terms on the Compare page.</p>
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

        <div className="flex flex-wrap items-center gap-3 border-t border-line-soft pt-5">
          <button className="btn-primary" disabled={!file || running || needsKey}>{running ? 'Analyzing…' : 'Start analysis'}</button>
          {needsKey ? (
            <Link to="/account" className="link text-sm">Add your OpenAI key first</Link>
          ) : !file && <span className="text-sm text-ink-muted">Choose a file to start.</span>}
        </div>
      </form>

      {job && job.status === 'failed' && <p className="notice-error mt-6 animate-fade-in">{job.error}</p>}
      {job && job.status !== 'failed' && <Progress job={job} />}
    </div>
  );
}
