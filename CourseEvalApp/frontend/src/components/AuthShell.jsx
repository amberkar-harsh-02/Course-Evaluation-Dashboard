import PropTypes from 'prop-types';

export default function AuthShell({ title, subtitle, children }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-page px-4">
      <div className="w-full max-w-sm">
        <p className="mb-6 text-center font-serif text-xl text-ink">Course Evaluation</p>
        <div className="card">
          <h1 className="font-serif text-xl font-medium text-ink">{title}</h1>
          {subtitle && <p className="mb-6 mt-1 text-sm text-ink-muted">{subtitle}</p>}
          {children}
        </div>
      </div>
    </div>
  );
}

AuthShell.propTypes = { title: PropTypes.string.isRequired, subtitle: PropTypes.string, children: PropTypes.node };
