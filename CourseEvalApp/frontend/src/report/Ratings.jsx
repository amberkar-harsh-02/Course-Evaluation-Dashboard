import PropTypes from 'prop-types';

const SHADES = ['#1F4E79', '#4F7AA3', '#8FAECB', '#C9D7E5', '#E4EAF1', '#F1F4F7'];

/** The survey's own multiple-choice questions, as found in the uploaded file. */
export default function Ratings({ ratings }) {
  if (!ratings.length) return null;
  return (
    <section aria-labelledby="ratings-title" className="border border-line bg-paper px-4 py-5 sm:px-6">
      <h2 id="ratings-title" className="section-title">Survey rating questions</h2>
      <p className="mt-1 text-sm text-ink-muted">Answers to the multiple-choice questions in the evaluation file, counted as they were submitted.</p>
      <ul className="mt-5 space-y-6">
        {ratings.map((r) => {
          const entries = Object.entries(r.distribution || {});
          const total = entries.reduce((sum, [, n]) => sum + n, 0) || 1;
          return (
            <li key={r.question}>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="max-w-[64ch] text-ink">{r.question}</p>
                <p className="num text-sm text-ink-muted">
                  {r.mean != null && <span className="mr-3 font-serif text-base font-medium text-ink">{r.mean.toFixed(2)} average</span>}
                  {r.n} answers
                </p>
              </div>
              <div className="mt-2 flex h-2.5 w-full overflow-hidden rounded-sm bg-line-soft" aria-hidden="true">
                {entries.map(([label, n], i) => (
                  <div key={label} style={{ width: `${(n / total) * 100}%`, background: SHADES[i % SHADES.length] }} />
                ))}
              </div>
              <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
                {entries.map(([label, n], i) => (
                  <li key={label} className="flex items-center gap-1.5">
                    <span className="inline-block h-2 w-2 rounded-sm" style={{ background: SHADES[i % SHADES.length] }} />
                    {label}: <span className="num text-ink-soft">{n}</span> ({Math.round((n / total) * 100)}%)
                  </li>
                ))}
              </ul>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

Ratings.propTypes = {
  ratings: PropTypes.arrayOf(PropTypes.shape({
    question: PropTypes.string, n: PropTypes.number, mean: PropTypes.number, distribution: PropTypes.object,
  })).isRequired,
};
