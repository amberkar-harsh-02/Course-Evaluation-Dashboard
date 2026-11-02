import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import PropTypes from 'prop-types';
import toast from 'react-hot-toast';
import { api, formatDate } from '../api';
import { OTHER_LABEL, buildView, cleanReport, downloadJson, formatScore, withIgnored } from '../report/model';
import { CategoryChart, OverallGrade, TopicCards } from '../report/Overview';
import TopicStats from '../report/TopicStats';
import TopicModal from '../report/TopicModal';
import CommentList from '../report/CommentList';
import { useReportNav } from '../reportNav';

function TopicPage({ topic, onBack, onSaveIgnored }) {
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [saving, setSaving] = useState(false);

  const start = () => {
    setSelected(new Set(topic.comments.filter((c) => c.ignored).map((c) => c.text)));
    setSelecting(true);
  };
  const toggle = (text) => setSelected((current) => {
    const next = new Set(current);
    if (next.has(text)) next.delete(text); else next.add(text);
    return next;
  });
  const save = async () => {
    setSaving(true);
    try {
      await onSaveIgnored(topic.topic, selected);
      setSelecting(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <button type="button" className="link text-sm" onClick={onBack}>Back to overview</button>
      <section className="card space-y-6">
        <h2 className="font-serif text-2xl font-medium text-ink">{topic.topic}</h2>
        <TopicStats topic={topic} />
      </section>

      <section className="card">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h3 className="section-title">Comments</h3>
          {!selecting ? (
            <button type="button" className="btn-secondary" onClick={start}>Ignore comments</button>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-ink-soft">{selected.size} selected</span>
              <button type="button" className="btn-secondary" onClick={() => setSelecting(false)} disabled={saving}>Cancel</button>
              <button type="button" className="btn-primary" onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save and recalculate'}</button>
            </div>
          )}
        </div>
        {selecting && (
          <p className="notice-info mb-4">Tick the comments that should not count toward this topic&apos;s score, then save. They stay visible, marked as ignored.</p>
        )}
        <CommentList
          comments={topic.comments}
          selecting={selecting}
          selected={selected}
          onToggle={toggle}
          idPrefix="topic"
          emptyText="No comments were assigned to this topic."
        />
      </section>
    </div>
  );
}

TopicPage.propTypes = { topic: PropTypes.object.isRequired, onBack: PropTypes.func.isRequired, onSaveIgnored: PropTypes.func.isRequired };

export default function ReportView() {
  const { reportId } = useParams();
  const [params, setParams] = useSearchParams();
  const [meta, setMeta] = useState(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const [modalTopic, setModalTopic] = useState(null);

  useEffect(() => {
    api(`/reports/${reportId}`)
      .then((result) => { setMeta(result); setReport(cleanReport(result.report)); })
      .catch((err) => setError(err.message));
  }, [reportId]);

  const view = useMemo(() => (report ? buildView(report) : null), [report]);

  // Tell the sidebar which report is open so it can list the topics; clear it when leaving the report
  const { setOpenReport } = useReportNav();
  useEffect(() => {
    if (!view || !meta) return;
    setOpenReport({
      id: reportId, course: meta.course, term: meta.term,
      topics: view.topics.map((t) => ({ topic: t.topic, average: t.average })),
    });
  }, [view, meta, reportId, setOpenReport]);
  useEffect(() => () => setOpenReport(null), [setOpenReport]);
  const pageTopic = params.get('topic');
  // Opening a topic from the sidebar replaces the page; start it at the top
  useEffect(() => { window.scrollTo(0, 0); setModalTopic(null); }, [pageTopic]);
  const openPage = useCallback((topic) => { setModalTopic(null); setParams({ topic }); window.scrollTo(0, 0); }, [setParams]);
  const closeModal = useCallback(() => setModalTopic(null), []);

  const saveIgnored = async (topic, ignoredTexts) => {
    const updated = withIgnored(report, topic, ignoredTexts);
    try {
      await api(`/reports/${reportId}`, { method: 'PUT', body: { report: updated } });
      const before = formatScore(report.overall_score);
      setReport(updated);
      toast.success(`Saved. Overall grade ${before} is now ${formatScore(updated.overall_score)}.`);
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

  const topicForPage = view.topics.find((t) => t.topic === pageTopic);
  const topicForModal = view.topics.find((t) => t.topic === modalTopic);
  const commentRows = view.allComments.map((c) => {
    const scores = Object.values(c.scores);
    return {
      text: c.text,
      question: c.question,
      topics: c.topics.filter((t) => t !== OTHER_LABEL),
      scores: c.scores,
      score: scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null,
      ignored: false,
    };
  });

  return (
    <div className="page max-w-6xl space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <Link to="/" className="link text-sm">My reports</Link>
          <h1 className="page-title mt-2">{meta.course}{meta.term ? <span className="text-ink-muted"> ({meta.term})</span> : null}</h1>
          <p className="mt-1 text-sm text-ink-muted">Analyzed {formatDate(meta.created_at)}</p>
        </div>
        <button type="button" className="btn-secondary"
                onClick={() => downloadJson(report, `${meta.course}${meta.term ? `_${meta.term}` : ''}_report.json`)}>
          Download JSON
        </button>
      </header>

      {topicForPage ? (
        <TopicPage topic={topicForPage} onBack={() => setParams({})} onSaveIgnored={saveIgnored} />
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
            <OverallGrade score={view.overall} comments={view.commentsAnalyzed} scoredTopics={view.topics.filter((t) => t.scored > 0).length} />
            <CategoryChart topics={view.topics} onSelect={setModalTopic} />
          </div>

          <TopicCards topics={view.topics} onSelect={setModalTopic} />

          <section aria-labelledby="comments-title">
            <h2 id="comments-title" className="section-title">Analyzed comments</h2>
            <p className="mt-1 mb-4 text-sm text-ink-muted">
              Every student comment once. With a topic selected, the score shown is the score for that topic.
            </p>
            <CommentList comments={commentRows} topicOptions={view.topics.map((t) => t.topic)} idPrefix="all" emptyText="This report has no comments." />
          </section>

          {view.notes.length > 0 && (
            <details className="text-sm text-ink-muted">
              <summary className="cursor-pointer text-ink-soft">Notes on this analysis ({view.notes.length})</summary>
              <ul className="mt-2 list-disc space-y-1 pl-5">{view.notes.map((n) => <li key={n}>{n}</li>)}</ul>
            </details>
          )}
        </>
      )}

      {topicForModal && <TopicModal topic={topicForModal} onClose={closeModal} onOpenPage={() => openPage(topicForModal.topic)} />}
    </div>
  );
}
