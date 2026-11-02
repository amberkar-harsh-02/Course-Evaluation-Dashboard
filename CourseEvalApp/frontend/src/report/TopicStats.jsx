import PropTypes from 'prop-types';
import { formatScore, scoreTone } from './model';
import { TONE_TEXT } from './Overview';

const SPREAD_BG = ['bg-score-low', 'bg-score-low', 'bg-score-mid', 'bg-score-high', 'bg-score-high'];

/** How many comments gave each rubric score, as five small bars. */
function ScoreSpread({ distribution }) {
  const most = Math.max(1, ...distribution);
  return (
    <div>
      <p className="text-xs font-medium text-ink-muted">Score spread</p>
      <div className="mt-2 flex items-end gap-3" role="img"
           aria-label={distribution.map((n, i) => `${n} comments gave ${i + 1}`).join(', ')}>
        {distribution.map((n, i) => (
          <div key={i} className="flex w-9 flex-col items-center gap-1">
            <span className="num text-xs text-ink-soft">{n}</span>
            <div className="flex h-12 w-full items-end rounded-sm bg-line-soft">
              <div className={`w-full origin-bottom animate-grow-up rounded-sm ${SPREAD_BG[i]}`} style={{ height: `${n ? Math.max(8, (n / most) * 100) : 0}%`, opacity: 0.85 }} />
            </div>
            <span className="num text-xs text-ink-muted">{i + 1}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

ScoreSpread.propTypes = { distribution: PropTypes.arrayOf(PropTypes.number).isRequired };

/** Numbers and summary for one topic, shared by the pop-up and the full topic page. */
export default function TopicStats({ topic }) {
  const { sentiment, directions } = topic;
  const paceTotal = directions ? (directions.too_fast || 0) + (directions.too_slow || 0) + (directions.appropriate || 0) : 0;
  return (
    <div className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-[auto_1fr_auto]">
        <div>
          <p className="text-xs font-medium text-ink-muted">Average score</p>
          <p className={`num mt-1 font-serif text-4xl font-medium ${TONE_TEXT[scoreTone(topic.average)]}`}>
            {formatScore(topic.average)}<span className="ml-1 text-base text-ink-muted">/ 5</span>
          </p>
          {topic.scored > 0 && topic.scored < 5 && <p className="mt-1 text-xs text-ink-muted">Few scored comments; an indication only</p>}
        </div>
        <dl className="grid grid-cols-[repeat(2,max-content)] content-start gap-x-10 gap-y-3 text-sm sm:border-l sm:border-line sm:pl-5">
          <div><dt className="text-xs text-ink-muted">Comments</dt><dd className="num font-medium">{topic.assigned}</dd></div>
          <div><dt className="text-xs text-ink-muted">Scored</dt><dd className="num font-medium">{topic.scored}</dd></div>
          <div className="col-span-2">
            <dt className="text-xs text-ink-muted">Sentiment</dt>
            <dd className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
              <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-score-high" />{sentiment.positive} positive</span>
              <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-score-mid" />{sentiment.neutral} neutral</span>
              <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-score-low" />{sentiment.negative} negative</span>
            </dd>
          </div>
        </dl>
        <ScoreSpread distribution={topic.distribution} />
      </div>

      {paceTotal > 0 && (
        <p className="rounded border border-line-soft bg-page px-4 py-3 text-sm text-ink-soft">
          Of {paceTotal} comments about pace, <strong className="font-medium text-ink">{directions.too_fast || 0}</strong> said too fast,{' '}
          <strong className="font-medium text-ink">{directions.too_slow || 0}</strong> said too slow and{' '}
          <strong className="font-medium text-ink">{directions.appropriate || 0}</strong> said about right.
        </p>
      )}

      {topic.summary && (
        <div>
          <p className="text-xs font-medium text-ink-muted">AI summary</p>
          <p className="mt-1 max-w-[72ch] font-serif text-lg leading-relaxed text-ink">{topic.summary}</p>
        </div>
      )}
      {topic.ignored > 0 && <p className="text-xs text-ink-muted">{topic.ignored} comments are ignored for this topic and not counted.</p>}
    </div>
  );
}

TopicStats.propTypes = { topic: PropTypes.object.isRequired };
