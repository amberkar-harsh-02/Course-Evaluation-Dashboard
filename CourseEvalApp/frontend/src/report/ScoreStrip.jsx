import PropTypes from 'prop-types';
import { formatScore, scoreTone } from './model';

const TONE_TEXT = { low: 'text-score-low', mid: 'text-score-mid', high: 'text-score-high', none: 'text-ink-muted' };
const TONE_BG = { low: 'bg-score-low', mid: 'bg-score-mid', high: 'bg-score-high', none: 'bg-ink-muted' };

// Position on the shared 1-5 rubric track, as a percentage
const position = (score) => `${((score - 1) / 4) * 100}%`;

/**
 * One topic on the 1-5 rubric track: a small bar for how many comments gave each score,
 * and a marker at the average. Every row uses the same track, so topics line up for comparison.
 */
export default function ScoreStrip({ average, distribution, faded = false }) {
  const most = Math.max(1, ...distribution);
  const tone = scoreTone(average);
  const total = distribution.reduce((a, b) => a + b, 0);
  const description = average == null
    ? 'No scored comments'
    : `Average ${formatScore(average)} out of 5 from ${total} scored comments: ${distribution.map((n, i) => `${n} gave ${i + 1}`).join(', ')}`;

  return (
    <div className={`relative mx-2 h-11 ${faded ? 'opacity-55' : ''}`} role="img" aria-label={description}>
      {/* track and the five rubric points */}
      <div className="absolute inset-x-0 bottom-2 h-px bg-line" />
      {[1, 2, 3, 4, 5].map((k) => (
        <div key={k} className="absolute bottom-0 -translate-x-1/2" style={{ left: position(k) }}>
          <div
            className="mx-auto w-3 rounded-t-sm bg-[#B9C3CF]"
            style={{ height: `${distribution[k - 1] ? 4 + (distribution[k - 1] / most) * 26 : 0}px`, marginBottom: '8px' }}
          />
        </div>
      ))}
      {[1, 2, 3, 4, 5].map((k) => (
        <span key={`t${k}`} className="absolute bottom-[3px] h-1.5 w-px -translate-x-1/2 bg-line" style={{ left: position(k) }} />
      ))}
      {average != null && (
        <div className="absolute bottom-0 top-0 -translate-x-1/2" style={{ left: position(average) }}>
          <div className={`mx-auto h-full w-0.5 ${TONE_BG[tone]}`} />
        </div>
      )}
    </div>
  );
}

ScoreStrip.propTypes = {
  average: PropTypes.number,
  distribution: PropTypes.arrayOf(PropTypes.number).isRequired,
  faded: PropTypes.bool,
};

export function ScoreValue({ value, className = '' }) {
  return <span className={`num font-serif font-medium ${TONE_TEXT[scoreTone(value)]} ${className}`}>{formatScore(value)}</span>;
}

ScoreValue.propTypes = { value: PropTypes.number, className: PropTypes.string };

// Labels under the shared track, shown once above the ledger
export function StripScale() {
  return (
    <div className="relative mx-2 h-5 text-xs text-ink-muted" aria-hidden="true">
      {[1, 2, 3, 4, 5].map((k) => (
        <span key={k} className="num absolute -translate-x-1/2" style={{ left: position(k) }}>{k}</span>
      ))}
    </div>
  );
}
