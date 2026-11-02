import { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { scoreTone, shortName } from './model';
import SearchField from '../components/SearchField';

const BADGE = {
  low: 'bg-score-lowTint text-score-low',
  mid: 'bg-line-soft text-score-mid',
  high: 'bg-score-highTint text-score-high',
  none: 'bg-line-soft text-ink-muted',
};
const SORTS = {
  original: { label: 'Original order', fn: () => 0 },
  low: { label: 'Lowest score first', fn: (a, b) => (a.score ?? 6) - (b.score ?? 6) },
  high: { label: 'Highest score first', fn: (a, b) => (b.score ?? 0) - (a.score ?? 0) },
};
const FILTERS = {
  all: { label: 'All scores', test: () => true },
  low: { label: 'Needs attention (1–2)', test: (c) => c.score !== null && c.score <= 2 },
  mid: { label: 'Mixed (3)', test: (c) => c.score === 3 },
  high: { label: 'Positive (4–5)', test: (c) => c.score !== null && c.score >= 4 },
  none: { label: 'Not scored', test: (c) => c.score === null },
};

/**
 * Student comments with search, filters and sort.
 * Each comment: { text, question, score, topics?: string[], scores?: {topic: score}, ignored }.
 * Pass `topicOptions` to add a topic filter; `selecting` adds checkboxes for ignore mode.
 */
export default function CommentList({ comments, topicOptions = null, selecting = false, selected, onToggle, emptyText, idPrefix = 'comments' }) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [topic, setTopic] = useState('all');
  const [sort, setSort] = useState('original');

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return comments
      // With a topic chosen, show and filter by that topic's score (comments can score differently per topic)
      .map((c, index) => ({ ...c, index, score: topic !== 'all' && c.scores?.[topic] != null ? c.scores[topic] : c.score }))
      .filter((c) => FILTERS[filter].test(c)
        && (topic === 'all' || c.topics?.includes(topic))
        && (!q || c.text.toLowerCase().includes(q)))
      .sort((a, b) => SORTS[sort].fn(a, b) || a.index - b.index);
  }, [comments, query, filter, topic, sort]);

  // When every comment answers the same survey question, say it once instead of on each comment
  const questions = [...new Set(comments.map((c) => c.question).filter(Boolean))];
  const sharedQuestion = questions.length === 1 ? questions[0] : null;

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-48 flex-1">
          <label className="label" htmlFor={`${idPrefix}-search`}>Search</label>
          <SearchField id={`${idPrefix}-search`} value={query} onChange={setQuery} placeholder="Search comments" />
        </div>
        {topicOptions && (
          <div>
            <label className="label" htmlFor={`${idPrefix}-topic`}>Topic</label>
            <select id={`${idPrefix}-topic`} className="input" value={topic} onChange={(e) => setTopic(e.target.value)}>
              <option value="all">All topics</option>
              {topicOptions.map((t) => <option key={t} value={t}>{shortName(t)}</option>)}
            </select>
          </div>
        )}
        <div>
          <label className="label" htmlFor={`${idPrefix}-filter`}>Score</label>
          <select id={`${idPrefix}-filter`} className="input" value={filter} onChange={(e) => setFilter(e.target.value)}>
            {Object.entries(FILTERS).map(([key, f]) => <option key={key} value={key}>{f.label}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor={`${idPrefix}-sort`}>Order</label>
          <select id={`${idPrefix}-sort`} className="input" value={sort} onChange={(e) => setSort(e.target.value)}>
            {Object.entries(SORTS).map(([key, s]) => <option key={key} value={key}>{s.label}</option>)}
          </select>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-baseline justify-between gap-2 text-sm">
        <p className="text-ink-muted" aria-live="polite">
          {visible.length === comments.length ? `${comments.length} comments` : `${visible.length} of ${comments.length} comments`}
        </p>
        {sharedQuestion && <p className="max-w-[72ch] text-ink-muted">Answers to: {sharedQuestion}</p>}
      </div>

      {visible.length === 0 ? (
        <p className="mt-4 rounded border border-dashed border-line px-4 py-6 text-center text-sm text-ink-muted">
          {comments.length === 0 ? emptyText : 'No comments match. Clear the search or pick another filter.'}
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-line-soft rounded border border-line bg-paper">
          {visible.map((c) => {
            const checked = selecting && selected?.has(c.text);
            const tone = scoreTone(c.score);
            return (
              <li key={c.index} className={`flex items-start gap-4 px-4 py-3.5 transition-colors ${checked ? 'bg-accent-tint' : ''}`}>
                {selecting && (
                  <input
                    type="checkbox"
                    className="mt-2 h-4 w-4 shrink-0 accent-accent"
                    checked={checked}
                    onChange={() => onToggle(c.text)}
                    aria-label={`Ignore this comment: ${c.text.slice(0, 60)}`}
                  />
                )}
                <span
                  className={`num flex h-9 w-9 shrink-0 items-center justify-center rounded font-serif text-base font-medium ${BADGE[tone]}`}
                  title={c.score === null ? 'No rubric score' : `Rubric score ${c.score} of 5`}
                >
                  {c.score === null ? '–' : c.score}
                </span>
                <div className="min-w-0 flex-1">
                  <p className={`max-w-[80ch] leading-relaxed ${c.ignored && !selecting ? 'text-ink-muted line-through decoration-ink-muted/40' : 'text-ink'}`}>{c.text}</p>
                  {(c.topics?.length > 0 || (c.question && !sharedQuestion) || (c.ignored && !selecting)) && (
                    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
                      {c.topics?.map((t) => (
                        <span key={t} className="rounded-sm bg-accent-tint px-2 py-0.5 font-medium text-accent" title={t}>{shortName(t)}</span>
                      ))}
                      {c.ignored && !selecting && <span className="rounded-sm bg-line-soft px-2 py-0.5 font-medium text-ink-soft">Ignored</span>}
                      {c.question && !sharedQuestion && <span className="max-w-[60ch] truncate text-ink-muted" title={c.question}>Answer to: {c.question}</span>}
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

CommentList.propTypes = {
  comments: PropTypes.arrayOf(PropTypes.shape({
    text: PropTypes.string.isRequired, question: PropTypes.string, score: PropTypes.number,
    topics: PropTypes.arrayOf(PropTypes.string), ignored: PropTypes.bool,
  })).isRequired,
  topicOptions: PropTypes.arrayOf(PropTypes.string),
  selecting: PropTypes.bool,
  selected: PropTypes.instanceOf(Set),
  onToggle: PropTypes.func,
  emptyText: PropTypes.string,
  idPrefix: PropTypes.string,
};
