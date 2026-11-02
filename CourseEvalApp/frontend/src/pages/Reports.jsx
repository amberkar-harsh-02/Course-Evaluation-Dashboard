import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, formatDate } from '../api';

const MAX_COMPARE = 8;

export default function Reports() {
  const navigate = useNavigate();
  const [reports, setReports] = useState(null);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState([]);

  const load = () => api('/reports').then(setReports).catch((err) => setError(err.message));
  useEffect(() => { load(); }, []);

  const toggle = (id) => setSelected((current) => (
    current.includes(id) ? current.filter((x) => x !== id) : current.length < MAX_COMPARE ? [...current, id] : current
  ));

  const remove = async (report) => {
    if (!window.confirm(`Delete the report for ${report.course}? This also deletes the uploaded file and cannot be undone.`)) return;
    try {
      await api(`/reports/${report.id}`, { method: 'DELETE' });
      setSelected((current) => current.filter((x) => x !== report.id));
      toast.success('Report deleted');
      load();
    } catch (err) {
      toast.error(err.message);
    }
  };

  return (
    <div className="page">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="page-title">My reports</h1>
          <p className="page-subtitle">Each report is the analysis of one course evaluation file. Only you can see your reports.</p>
        </div>
        <Link to="/new" className="btn-primary">New analysis</Link>
      </div>

      {error && <p className="notice-error mb-4">{error}</p>}
      {reports === null && !error && <p className="text-sm text-ink-muted">Loading…</p>}

      {reports?.length === 0 && (
        <div className="card text-center">
          <p className="font-medium text-ink">No reports yet</p>
          <p className="mt-1 text-sm text-ink-muted">Upload an evaluation file (PDF, Excel, CSV or Word) to create your first report.</p>
          <Link to="/new" className="btn-primary mt-4">Start an analysis</Link>
        </div>
      )}

      {reports?.length > 1 && (
        <div className="mb-3 flex items-center justify-between rounded border border-line bg-paper px-4 py-2 text-sm">
          <span className="text-ink-soft">
            {selected.length === 0
              ? 'Tick two or more reports to compare them across terms.'
              : `${selected.length} selected${selected.length === MAX_COMPARE ? ' (maximum)' : ''}`}
          </span>
          <div className="flex gap-2">
            {selected.length > 0 && <button className="btn-secondary py-1" onClick={() => setSelected([])}>Clear</button>}
            <button
              className="btn-primary py-1"
              disabled={selected.length < 2}
              onClick={() => navigate(`/compare?ids=${selected.join(',')}`)}
            >
              Compare
            </button>
          </div>
        </div>
      )}

      {reports?.length > 0 && (
        <div className="card overflow-x-auto p-0">
          <table className="table">
            <thead>
              <tr>
                {reports.length > 1 && <th className="w-8"><span className="sr-only">Select</span></th>}
                <th>Course</th>
                <th>Term</th>
                <th>Created</th>
                <th className="text-right">Overall score</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {reports.map((report) => (
                <tr key={report.id} className={selected.includes(report.id) ? 'bg-accent-tint' : ''}>
                  {reports.length > 1 && (
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Select ${report.course} ${report.term || ''} for comparison`}
                        className="h-4 w-4 accent-accent"
                        checked={selected.includes(report.id)}
                        onChange={() => toggle(report.id)}
                      />
                    </td>
                  )}
                  <td>
                    <Link to={`/reports/${report.id}`} className="font-medium text-accent hover:underline">{report.course}</Link>
                    <p className="text-xs text-ink-muted">{report.original_filename}</p>
                  </td>
                  <td className="text-ink-soft">{report.term || '—'}</td>
                  <td className="text-ink-soft">{formatDate(report.created_at)}</td>
                  <td className="text-right font-medium tabular-nums">{report.overall_score != null ? `${report.overall_score.toFixed(2)} / 5` : '—'}</td>
                  <td className="text-right">
                    <button className="text-xs font-medium text-score-low hover:underline" onClick={() => remove(report)}>Delete</button>
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
