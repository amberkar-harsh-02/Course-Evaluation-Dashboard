import PropTypes from 'prop-types';

/** Page numbers to show: always the first and last, the current page and its neighbours, "…" for gaps. */
function pageWindow(page, pageCount) {
  const pages = new Set([1, pageCount, page - 1, page, page + 1].filter((p) => p >= 1 && p <= pageCount));
  const sorted = [...pages].sort((a, b) => a - b);
  const out = [];
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] > 1) out.push(p - sorted[i - 1] === 2 ? p - 1 : `gap-${p}`);
    out.push(p);
  });
  return out;
}

const buttonClass = 'inline-flex h-8 min-w-8 items-center justify-center rounded-md px-2.5 text-sm transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40';

/** First / Previous / page numbers / Next / Last, plus how many items to show per page. */
export default function Pagination({ page, pageCount, onPage, pageSize, pageSizes, onPageSize, label, idPrefix }) {
  const go = (p) => onPage(Math.min(Math.max(1, p), pageCount));
  return (
    <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
      {pageCount > 1 ? (
        <nav aria-label={label} className="flex flex-wrap items-center gap-1">
          <button type="button" className={`${buttonClass} text-ink-soft hover:bg-line-soft`} onClick={() => go(1)} disabled={page === 1}>First</button>
          <button type="button" className={`${buttonClass} text-ink-soft hover:bg-line-soft`} onClick={() => go(page - 1)} disabled={page === 1}>Previous</button>
          {pageWindow(page, pageCount).map((p) => (typeof p === 'string' ? (
            <span key={p} className="px-1 text-sm text-ink-muted" aria-hidden="true">…</span>
          ) : (
            <button
              key={p}
              type="button"
              onClick={() => go(p)}
              aria-current={p === page ? 'page' : undefined}
              aria-label={`Page ${p}`}
              className={`${buttonClass} num ${p === page ? 'bg-accent font-medium text-accent-on' : 'text-ink-soft hover:bg-line-soft'}`}
            >
              {p}
            </button>
          )))}
          <button type="button" className={`${buttonClass} text-ink-soft hover:bg-line-soft`} onClick={() => go(page + 1)} disabled={page === pageCount}>Next</button>
          <button type="button" className={`${buttonClass} text-ink-soft hover:bg-line-soft`} onClick={() => go(pageCount)} disabled={page === pageCount}>Last</button>
        </nav>
      ) : <span />}
      <label className="flex items-center gap-2 text-sm text-ink-muted" htmlFor={`${idPrefix}-page-size`}>
        Show
        <select id={`${idPrefix}-page-size`} className="input h-8 w-20" value={pageSize} onChange={(e) => onPageSize(Number(e.target.value))}>
          {pageSizes.map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
        per page
      </label>
    </div>
  );
}

Pagination.propTypes = {
  page: PropTypes.number.isRequired,
  pageCount: PropTypes.number.isRequired,
  onPage: PropTypes.func.isRequired,
  pageSize: PropTypes.number.isRequired,
  pageSizes: PropTypes.arrayOf(PropTypes.number).isRequired,
  onPageSize: PropTypes.func.isRequired,
  label: PropTypes.string.isRequired,
  idPrefix: PropTypes.string.isRequired,
};
