import { useState } from 'react';
import PropTypes from 'prop-types';
import ScoreStrip, { ScoreValue, StripScale } from './ScoreStrip';
import CommentList from './CommentList';

const RELIABILITY_NOTE = {
  low_sample: 'Few scored comments; treat as an indication only',
  mixed_confidence: 'Some scores are low-confidence',
  needs_review: 'Some comments could not be scored',
  unscored: 'No scored comments',
};

function PaceDirections({ directions }) {
  const total = (directions.too_fast || 0) + (directions.too_slow || 0) + (directions.appropriate || 0);
  if (!total) return null;
  return (
    <p className="text-sm text-ink-soft">
      Of {total} comments about pace, <strong className="font-medium text-ink">{directions.too_fast || 0}</strong> said too fast,{' '}
      <strong className="font-medium text-ink">{directions.too_slow || 0}</strong> said too slow and{' '}
      <strong className="font-medium text-ink">{directions.appropriate || 0}</strong> said about right.
    </p>
  );
}

PaceDirections.propTypes = { directions: PropTypes.object.isRequired };

function TopicDetail({ topic, onSaveIgnored }) {
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState(new Set());

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
    await onSaveIgnored(topic.topic, selected);
    setSelecting(false);
  };

  return (
    <div className="border-t border-line-soft bg-page/60 px-4 pb-6 pt-5 sm:px-6">
      {topic.summary && <p className="max-w-[72ch] font-serif text-lg leading-relaxed text-ink">{topic.summary}</p>}
      <div className="mt-3 space-y-1">
        {topic.directions && <PaceDirections directions={topic.directions} />}
        <p className="text-sm text-ink-muted">
          {topic.assigned} comments mention this topic; {topic.scored} have a rubric score
          {topic.ignored > 0 ? `; ${topic.ignored} ignored by you` : ''}.
        </p>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        {!selecting ? (
          <button className="btn-secondary" onClick={start}>Choose comments to ignore</button>
        ) : (
          <>
            <p className="text-sm text-ink-soft">
              Tick comments that should not count toward this topic&apos;s score. {selected.size} ticked.
            </p>
            <button className="btn-primary" onClick={save}>Save and recalculate</button>
            <button className="btn-secondary" onClick={() => setSelecting(false)}>Cancel</button>
          </>
        )}
      </div>

      <div className="mt-5">
        <CommentList
          comments={topic.comments}
          selecting={selecting}
          selected={selected}
          onToggle={toggle}
          emptyText="No comments were assigned to this topic."
        />
      </div>
    </div>
  );
}

TopicDetail.propTypes = { topic: PropTypes.object.isRequired, onSaveIgnored: PropTypes.func.isRequired };

/**
 * The report's main view: every teaching topic on one shared 1-5 rubric track.
 * Open a row to read its summary and comments, and to ignore comments.
 */
export default function TopicLedger({ topics, onSaveIgnored, initialTopic = null }) {
  const [open, setOpen] = useState(initialTopic);

  return (
    <section aria-labelledby="ledger-title" className="border border-line bg-paper">
      <div className="flex flex-wrap items-end justify-between gap-2 px-4 pb-3 pt-5 sm:px-6">
        <div>
          <h2 id="ledger-title" className="section-title">Teaching topics</h2>
          <p className="mt-1 text-sm text-ink-muted">Average rubric score per topic. The small bars show how many comments gave each score.</p>
        </div>
      </div>

      <div className="hidden grid-cols-[minmax(0,15rem)_3.5rem_minmax(0,1fr)_5rem] items-end gap-4 border-b border-line px-6 pb-1 md:grid">
        <span className="text-xs text-ink-muted">Topic</span>
        <span className="text-right text-xs text-ink-muted">Score</span>
        <StripScale />
        <span className="text-right text-xs text-ink-muted">Scored</span>
      </div>

      <ul>
        {topics.map((t) => {
          const isOpen = open === t.topic;
          const note = RELIABILITY_NOTE[t.reliability];
          return (
            <li key={t.topic} className="border-b border-line-soft last:border-b-0">
              <button
                type="button"
                className={`grid w-full grid-cols-[minmax(0,1fr)_3.5rem] items-center gap-x-4 gap-y-1 px-4 py-3 text-left transition-colors hover:bg-page sm:px-6 md:grid-cols-[minmax(0,15rem)_3.5rem_minmax(0,1fr)_5rem] ${isOpen ? 'bg-page' : ''}`}
                aria-expanded={isOpen}
                onClick={() => setOpen(isOpen ? null : t.topic)}
              >
                <span className="min-w-0">
                  <span className="block font-medium text-ink">{t.topic}</span>
                  {note && <span className="block text-xs text-ink-muted">{note}</span>}
                </span>
                <ScoreValue value={t.average} className="text-right text-xl" />
                <span className="col-span-2 md:col-span-1"><ScoreStrip average={t.average} distribution={t.distribution} faded={t.scored < 5} /></span>
                <span className="num hidden text-right text-sm text-ink-muted md:block">{t.scored}</span>
              </button>
              {isOpen && <TopicDetail topic={t} onSaveIgnored={onSaveIgnored} />}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

TopicLedger.propTypes = {
  topics: PropTypes.arrayOf(PropTypes.object).isRequired,
  onSaveIgnored: PropTypes.func.isRequired,
  initialTopic: PropTypes.string,
};
