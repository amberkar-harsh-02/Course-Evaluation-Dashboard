import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import PropTypes from 'prop-types';
import { api } from '../api';

const label = (report) => report.term || report.course;
const fmt = (value) => (value === null || value === undefined ? '—' : value.toFixed(2));

function Change({ value, muted = false }) {
  if (value === null || value === undefined) return <span className="text-slate-400">—</span>;
  const tone = muted ? 'text-slate-400' : value > 0 ? 'text-green-700' : value < 0 ? 'text-red-700' : 'text-slate-500';
  const sign = value > 0 ? '+' : value < 0 ? '−' : '±';
  return <span className={`tabular-nums font-medium ${tone}`}>{sign}{Math.abs(value).toFixed(2)}</span>;
}

Change.propTypes = { value: PropTypes.number, muted: PropTypes.bool };

const PALETTE = ['#1e3a8a', '#0f766e', '#b45309', '#7c3aed', '#be123c', '#475569'];

export default function Compare() {
  const [params] = useSearchParams();
  const ids = params.get('ids') || '';
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [chartTopics, setChartTopics] = useState([]);

  useEffect(() => {
    setData(null);
    api(`/compare?ids=${encodeURIComponent(ids)}`)
      .then((result) => {
        setData(result);
        // Start the chart with the topics that changed the most
        const moved = [...result.improved, ...result.declined].map((item) => item.topic);
        setChartTopics(moved.slice(0, 3));
      })
      .catch((err) => setError(err.message));
  }, [ids]);

  if (error) {
    return (
      <div className="page">
        <p className="notice-error">{error}</p>
        <Link to="/" className="btn-secondary mt-4">Back to my reports</Link>
      </div>
    );
  }
  if (!data) return <div className="page text-sm text-slate-500">Loading comparison…</div>;

  const { reports } = data;
  const chartRows = reports.map((report, index) => {
    const row = { name: label(report), Overall: report.overall_score };
    data.topics.forEach((topic) => {
      if (chartTopics.includes(topic.topic)) row[topic.topic] = topic.cells[index]?.average_score ?? null;
    });
    return row;
  });
  const hasPace = reports.some((r) => r.pace_directions);
  const toggleTopic = (topic) => setChartTopics((current) => (
    current.includes(topic) ? current.filter((t) => t !== topic) : [...current, topic].slice(-5)
  ));

  return (
    <div className="page max-w-6xl space-y-6">
      <div>
        <Link to="/" className="text-sm text-blue-800 hover:underline">← My reports</Link>
        <h1 className="page-title mt-2">Compare reports</h1>
        <p className="page-subtitle">
          {reports.map((r) => `${r.course}${r.term ? ` (${r.term})` : ''}`).join(' → ')}
        </p>
      </div>

      {data.warnings.length > 0 && (
        <div className="notice-info space-y-1">
          {data.warnings.map((warning) => <p key={warning}>{warning}</p>)}
        </div>
      )}

      {/* Headline numbers */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card">
          <p className="text-sm text-slate-500">Overall score, {label(reports[0])} → {label(reports[reports.length - 1])}</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            {fmt(reports[0].overall_score)} → {fmt(reports[reports.length - 1].overall_score)}
          </p>
          <p className="mt-1 text-sm"><Change value={data.overall_change} /> on a 1–5 scale</p>
        </div>
        <div className="card">
          <p className="text-sm font-medium text-slate-700">Most improved</p>
          {data.improved.length === 0 ? <p className="mt-2 text-sm text-slate-500">No clear improvement.</p> : (
            <ul className="mt-2 space-y-1 text-sm">
              {data.improved.map((item) => (
                <li key={item.topic} className="flex justify-between gap-3"><span>{item.topic}</span><Change value={item.change} /></li>
              ))}
            </ul>
          )}
        </div>
        <div className="card">
          <p className="text-sm font-medium text-slate-700">Most declined</p>
          {data.declined.length === 0 ? <p className="mt-2 text-sm text-slate-500">No clear decline.</p> : (
            <ul className="mt-2 space-y-1 text-sm">
              {data.declined.map((item) => (
                <li key={item.topic} className="flex justify-between gap-3"><span>{item.topic}</span><Change value={item.change} /></li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Trend chart */}
      <section className="card">
        <h2 className="text-base font-semibold text-slate-900">Trend</h2>
        <p className="mt-1 text-sm text-slate-500">Overall score, plus the topics you tick in the table below (up to five).</p>
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartRows} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
              <YAxis domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} stroke="#64748b" fontSize={12} />
              <Tooltip formatter={(value) => (value == null ? '—' : Number(value).toFixed(2))} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="Overall" stroke="#0f172a" strokeWidth={2.5} dot={{ r: 4 }} connectNulls isAnimationActive={false} />
              {chartTopics.map((topic, i) => (
                <Line key={topic} type="monotone" dataKey={topic} stroke={PALETTE[i % PALETTE.length]} strokeWidth={1.75} dot={{ r: 3 }} connectNulls isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Topic table */}
      <section className="card overflow-x-auto p-0">
        <div className="px-6 pt-5">
          <h2 className="text-base font-semibold text-slate-900">Scores by topic</h2>
          <p className="mt-1 text-sm text-slate-500">Average rubric score (1–5). <span className="text-slate-400">Grey</span> means fewer than 5 scored comments.</p>
        </div>
        <table className="table mt-3">
          <thead>
            <tr>
              <th className="w-10"><span className="sr-only">Show in chart</span></th>
              <th>Topic</th>
              {reports.map((r) => <th key={r.id} className="text-right">{label(r)}</th>)}
              <th className="text-right">Change</th>
            </tr>
          </thead>
          <tbody>
            <tr className="bg-slate-50 font-medium">
              <td />
              <td>Overall</td>
              {reports.map((r) => <td key={r.id} className="text-right tabular-nums">{fmt(r.overall_score)}</td>)}
              <td className="text-right"><Change value={data.overall_change} /></td>
            </tr>
            {data.topics.map((row) => (
              <tr key={row.topic}>
                <td>
                  <input
                    type="checkbox"
                    aria-label={`Show ${row.topic} in chart`}
                    className="h-4 w-4 accent-blue-800"
                    checked={chartTopics.includes(row.topic)}
                    onChange={() => toggleTopic(row.topic)}
                  />
                </td>
                <td>{row.topic}</td>
                {row.cells.map((cell, i) => (
                  <td key={reports[i].id} className={`text-right tabular-nums ${cell?.low_sample ? 'text-slate-400' : ''}`}
                      title={cell ? `${cell.scored_comments} scored comments` : 'Not in this report'}>
                    {fmt(cell?.average_score)}
                  </td>
                ))}
                <td className="text-right"><Change value={row.change} muted={!row.change_is_reliable} /></td>
              </tr>
            ))}
            {reports.some((r) => r.general_sentiment != null) && (
              <tr>
                <td />
                <td className="text-slate-600">General praise or criticism (no specific topic)</td>
                {reports.map((r) => <td key={r.id} className="text-right tabular-nums text-slate-600">{fmt(r.general_sentiment)}</td>)}
                <td />
              </tr>
            )}
          </tbody>
        </table>
      </section>

      {hasPace && (
        <section className="card overflow-x-auto p-0">
          <div className="px-6 pt-5">
            <h2 className="text-base font-semibold text-slate-900">Pace: what students said</h2>
          </div>
          <table className="table mt-3">
            <thead>
              <tr>
                <th>Comments saying the pace was…</th>
                {reports.map((r) => <th key={r.id} className="text-right">{label(r)}</th>)}
              </tr>
            </thead>
            <tbody>
              {[['too_fast', 'Too fast'], ['too_slow', 'Too slow'], ['appropriate', 'About right']].map(([key, name]) => (
                <tr key={key}>
                  <td>{name}</td>
                  {reports.map((r) => <td key={r.id} className="text-right tabular-nums">{r.pace_directions ? r.pace_directions[key] ?? 0 : '—'}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {data.ratings.length > 0 && (
        <section className="card overflow-x-auto p-0">
          <div className="px-6 pt-5">
            <h2 className="text-base font-semibold text-slate-900">Survey rating questions</h2>
            <p className="mt-1 text-sm text-slate-500">Average answers to the multiple-choice questions found in both files (scale as in the original survey).</p>
          </div>
          <table className="table mt-3">
            <thead>
              <tr>
                <th>Question</th>
                {reports.map((r) => <th key={r.id} className="text-right">{label(r)}</th>)}
                <th className="text-right">Change</th>
              </tr>
            </thead>
            <tbody>
              {data.ratings.map((row) => (
                <tr key={row.question}>
                  <td className="max-w-md">{row.question}</td>
                  {row.means.map((mean, i) => <td key={reports[i].id} className="text-right tabular-nums">{fmt(mean)}</td>)}
                  <td className="text-right"><Change value={row.change} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
