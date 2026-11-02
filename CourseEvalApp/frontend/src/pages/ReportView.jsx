import { useMemo, useState, useEffect } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, formatDate } from '../api';
import { buildView, cleanReport, downloadJson, formatScore, scoreTone, withIgnored } from '../report/model';
import TopicLedger from '../report/TopicLedger';
import CommentList from '../report/CommentList';
import Ratings from '../report/Ratings';

const OVERALL_TEXT = { low: 'text-score-low', mid: 'text-score-mid', high: 'text-score-high', none: 'text-ink-muted' };

export default function ReportView() {
  const { reportId } = useParams();
  const [params] = useSearchParams();
  const [meta, setMeta] = useState(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('topics');

  useEffect(() => {
    api(`/reports/${reportId}`)
      .then((result) => { setMeta(result); setReport(cleanReport(result.report)); })
      .catch((err) => setError(err.message));
  }, [reportId]);

  const view = useMemo(() => (report ? buildView(report) : null), [report]);

  const saveIgnored = async (topic, ignoredTexts) => {
    const updated = withIgnored(report, topic, ignoredTexts);
    try {
      await api(`/reports/${reportId}`, { method: 'PUT', body: { report: updated } });
      const before = formatScore(report.overall_score);
      setReport(updated);
      toast.success(`Saved. Overall score ${before} is now ${formatScore(updated.overall_score)}.`);
    } catch (err) {
      toast.error(`Not saved: ${err.message}`);
      throw err;
    }
  };

  if (error) {
    return (
      <div className="page">
        <p className="notice-error">{error}</p>
        <Link to="/" className="btn-secondary mt-4">Back to my reports</Link>
      </div>
    );
  }
  if (!view) return <div className="page text-sm text-ink-muted">Loading report…</div>;

  const general = view.general?.scored_comments ? view.general : null;
  const ignoredTotal = view.topics.reduce((sum, t) => sum + t.ignored, 0);

  return (
    <div className="page max-w-6xl space-y-8">
      <header>
        <Link to="/" className="link text-sm">My reports</Link>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-6">
          <div className="min-w-0">
            <h1 className="page-title">{meta.course}</h1>
            <p className="mt-1 text-sm text-ink-muted">
              {meta.term ? `${meta.term}, ` : ''}analyzed {formatDate(meta.created_at)} from {view.commentsAnalyzed} student comments
            </p>
          </div>
          <button className="btn-secondary" onClick={() => downloadJson(report, `${meta.course}${meta.term ? `_${meta.term}` : ''}_report.json`)}>
            Download JSON
          </button>
        </div>
      </header>

      {/* Headline: the overall score in the rubric's own terms */}
      <section className="grid gap-6 border border-line bg-paper px-6 py-6 md:grid-cols-[auto_1fr]">
        <div>
          <p className="text-sm text-ink-muted">Overall rubric score</p>
          <p className={`num mt-1 font-serif text-5xl font-medium ${OVERALL_TEXT[scoreTone(view.overall)]}`}>
            {formatScore(view.overall)}<span className="ml-1 text-xl text-ink-muted">/ 5</span>
          </p>
        </div>
        <div className="space-y-2 text-sm text-ink-soft md:border-l md:border-line md:pl-6">
          <p>
            The average of each comment&apos;s topic scores across {view.topics.filter((t) => t.scored > 0).length} teaching topics.
            {ignoredTotal > 0 && ` ${ignoredTotal} comment ${ignoredTotal === 1 ? 'assignment is' : 'assignments are'} ignored at your request.`}
          </p>
          {general && (
            <p>
              Comments with general praise or criticism but no specific topic ({general.scored_comments}) average{' '}
              <span className="num font-medium text-ink">{formatScore(general.average_score)}</span>; they are not part of the overall score.
            </p>
          )}
          {view.notes.length > 0 && (
            <details className="text-ink-muted">
              <summary className="cursor-pointer text-ink-soft">Notes on this analysis ({view.notes.length})</summary>
              <ul className="mt-2 list-disc space-y-1 pl-5">{view.notes.map((n) => <li key={n}>{n}</li>)}</ul>
            </details>
          )}
        </div>
      </section>

      <nav className="flex gap-6 border-b border-line text-sm" aria-label="Report sections">
        {[['topics', 'Topics'], ['comments', `All comments (${view.allComments.length})`], ...(view.ratings.length ? [['ratings', 'Survey ratings']] : [])].map(([key, name]) => (
          <button
            key={key}
            className={`-mb-px border-b-2 pb-2 ${tab === key ? 'border-accent font-medium text-ink' : 'border-transparent text-ink-muted hover:text-ink'}`}
            onClick={() => setTab(key)}
            aria-current={tab === key ? 'page' : undefined}
          >
            {name}
          </button>
        ))}
      </nav>

      {tab === 'topics' && (
        <div className="space-y-6">
          <TopicLedger topics={view.topics} onSaveIgnored={saveIgnored} initialTopic={params.get('topic')} />
          {view.other && view.other.comments.length > 0 && (
            <section className="border border-line bg-paper px-4 py-5 sm:px-6">
              <h2 className="section-title">Not about a specific topic</h2>
              <p className="mt-1 max-w-[72ch] text-sm text-ink-muted">
                {view.other.comments.length} comments were general, off-topic or answered a question about the student rather than the
                teaching. They are not scored by topic.
              </p>
              {view.other.summary && <p className="mt-3 max-w-[72ch] font-serif text-lg leading-relaxed">{view.other.summary}</p>}
              <details className="mt-4">
                <summary className="cursor-pointer text-sm font-medium text-accent">Read these comments</summary>
                <div className="mt-4"><CommentList comments={view.other.comments} emptyText="None." /></div>
              </details>
            </section>
          )}
        </div>
      )}

      {tab === 'comments' && (
        <section className="border border-line bg-paper px-4 py-5 sm:px-6">
          <h2 className="section-title">All comments</h2>
          <p className="mt-1 mb-5 text-sm text-ink-muted">Every student comment once, with the topics it was assigned to. Topic scores are in brackets; the number on the right is their average, rounded.</p>
          <CommentList
            showTopics
            emptyText="This report has no comments."
            comments={view.allComments.map((c) => {
              const scores = Object.values(c.scores);
              return {
                text: c.text,
                question: c.question,
                topics: c.topics.filter((t) => t !== 'None of the above / Other').map((t) => (c.scores[t] != null ? `${t} (${c.scores[t]})` : t)),
                score: scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null,
                ignored: false,
              };
            })}
          />
        </section>
      )}

      {tab === 'ratings' && <Ratings ratings={view.ratings} />}
    </div>
  );
}
