import { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { formatScore, scoreTone } from './model';

const RULE = { low: 'border-score-low', mid: 'border-score-mid', high: 'border-score-high', none: 'border-line' };
const TEXT = { low: 'text-score-low', mid: 'text-score-mid', high: 'text-score-high', none: 'text-ink-muted' };
const SORTS = {
  original: { label: 'Original order', fn: () => 0 },
  low: { label: 'Lowest score first', fn: (a, b) => (a.score ?? 6) - (b.score ?? 6) },
  high: { label: 'Highest score first', fn: (a, b) => (b.score ?? 0) - (a.score ?? 0) },
};
const FILTERS = {
  all: { label: 'All scores', test: () => true },
  low: { label: 'Scored 1 or 2', test: (c) => c.score !== null && c.score <= 2 },
  mid: { label: 'Scored 3', test: (c) => c.score === 3 },
  high: { label: 'Scored 4 or 5', test: (c) => c.score !== null && c.score >= 4 },
  none: { label: 'Not scored', test: (c) => c.score === null },
};

/**
 * Student comments with search, score filter and sort.
 * Each comment: { text, question, score, topics?, ignored, selected? }.
 */
export default function CommentList({ comments, showTopics = false, selecting = false, selected, onToggle, emptyText }) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState('original');

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return comments
      .map((c, index) => ({ ...c, index }))
      .filter((c) => FILTERS[filter].test(c) && (!q || c.text.toLowerCase().includes(q)))
      .sort((a, b) => SORTS[sort].fn(a, b) || a.index - b.index);
  }, [comments, query, filter, sort]);

  // When every comment answers the same survey question, say it once instead of on each comment
  const questions = [...new Set(comments.map((c) => c.question).filter(Boolean))];
  const sharedQuestion = questions.length === 1 ? questions[0] : null;

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-48 flex-1">
          <label className="label" htmlFor="comment-search">Search comments</label>
          <input id="comment-search" className="input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. office hours" />
        </div>
        <div>
          <label className="label" htmlFor="comment-filter">Show</label>
          <select id="comment-filter" className="input" value={filter} onChange={(e) => setFilter(e.target.value)}>
            {Object.entries(FILTERS).map(([key, f]) => <option key={key} value={key}>{f.label}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="comment-sort">Order</label>
          <select id="comment-sort" className="input" value={sort} onChange={(e) => setSort(e.target.value)}>
            {Object.entries(SORTS).map(([key, s]) => <option key={key} value={key}>{s.label}</option>)}
          </select>
        </div>
      </div>
      {sharedQuestion && <p className="mt-4 max-w-[72ch] text-sm text-ink-soft">Answers to: {sharedQuestion}</p>}
      <p className="mt-3 text-sm text-ink-muted" aria-live="polite">
        {visible.length === comments.length ? `${comments.length} comments` : `${visible.length} of ${comments.length} comments`}
      </p>

      {visible.length === 0 ? (
        <p className="mt-4 text-sm text-ink-muted">{comments.length === 0 ? emptyText : 'No comments match. Clear the search or choose another score.'}</p>
      ) : (
        <ul className="mt-3 space-y-3">
          {visible.map((c) => {
            const checked = selecting && selected?.has(c.text);
            const tone = scoreTone(c.score);
            const body = (
              <>
                <div className="flex items-start gap-4">
                  {selecting && (
                    <input
                      type="checkbox"
                      className="mt-1 h-4 w-4 shrink-0 accent-accent"
                      checked={checked}
                      onChange={() => onToggle(c.text)}
                      aria-label={`Ignore this comment: ${c.text.slice(0, 60)}`}
                    />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className={`max-w-[72ch] leading-relaxed ${c.ignored && !selecting ? 'text-ink-muted line-through decoration-ink-muted/40' : 'text-ink'}`}>{c.text}</p>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
                      {c.question && !sharedQuestion && <span className="max-w-[60ch] truncate" title={c.question}>Answer to: {c.question}</span>}
                      {showTopics && c.topics?.length > 0 && <span>Topics: {c.topics.join(', ')}</span>}
                      {c.ignored && !selecting && <span className="font-medium text-ink-soft">Ignored for this topic</span>}
                    </div>
                  </div>
                  <span className={`num shrink-0 font-serif text-lg font-medium ${TEXT[tone]}`}
                        title={c.score === null ? 'No rubric score' : `Rubric score ${c.score} of 5`}>
                    {c.score === null ? '—' : formatScore(c.score, 0)}
                  </span>
                </div>
              </>
            );
            return (
              <li key={c.index} className={`border-l-2 bg-paper py-3 pl-4 pr-4 ${RULE[tone]} ${checked ? 'ring-1 ring-accent' : ''}`}>
                {body}
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
  showTopics: PropTypes.bool,
  selecting: PropTypes.bool,
  selected: PropTypes.instanceOf(Set),
  onToggle: PropTypes.func,
  emptyText: PropTypes.string,
};
