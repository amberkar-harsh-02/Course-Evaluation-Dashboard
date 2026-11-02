import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, formatDate } from '../api';

export default function Reports() {
  const [reports, setReports] = useState(null);
  const [error, setError] = useState('');

  const load = () => api('/reports').then(setReports).catch((err) => setError(err.message));
  useEffect(() => { load(); }, []);

  const remove = async (report) => {
    if (!window.confirm(`Delete the report for ${report.course}? This also deletes the uploaded file and cannot be undone.`)) return;
    try {
      await api(`/reports/${report.id}`, { method: 'DELETE' });
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
      {reports === null && !error && <p className="text-sm text-slate-500">Loading…</p>}

      {reports?.length === 0 && (
        <div className="card text-center">
          <p className="font-medium text-slate-800">No reports yet</p>
          <p className="mt-1 text-sm text-slate-500">Upload an evaluation file (PDF, Excel, CSV or Word) to create your first report.</p>
          <Link to="/new" className="btn-primary mt-4">Start an analysis</Link>
        </div>
      )}

      {reports?.length > 0 && (
        <div className="card overflow-x-auto p-0">
          <table className="table">
            <thead>
              <tr>
                <th>Course</th>
                <th>Term</th>
                <th>Created</th>
                <th className="text-right">Overall score</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {reports.map((report) => (
                <tr key={report.id}>
                  <td>
                    <Link to={`/reports/${report.id}`} className="font-medium text-blue-800 hover:underline">{report.course}</Link>
                    <p className="text-xs text-slate-500">{report.original_filename}</p>
                  </td>
                  <td className="text-slate-600">{report.term || '—'}</td>
                  <td className="text-slate-600">{formatDate(report.created_at)}</td>
                  <td className="text-right font-medium tabular-nums">{report.overall_score != null ? `${report.overall_score.toFixed(2)} / 5` : '—'}</td>
                  <td className="text-right">
                    <button className="text-xs font-medium text-red-700 hover:underline" onClick={() => remove(report)}>Delete</button>
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
