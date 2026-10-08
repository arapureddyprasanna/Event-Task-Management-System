export function LoadingState({ label = 'Loading…' }) {
  return <div className="state-card" role="status"><span className="spinner" aria-hidden="true" />{label}</div>;
}

export function EmptyState({ title, children }) {
  return <div className="state-card empty-state"><span className="empty-icon" aria-hidden="true">✳</span><h3>{title}</h3>{children && <div className="empty-copy">{children}</div>}</div>;
}

export function ErrorState({ message, onRetry }) {
  return <div className="state-card error-state" role="alert"><p>{message}</p>{onRetry && <button className="button button-quiet" type="button" onClick={onRetry}>Try again</button>}</div>;
}

export function PageHeader({ eyebrow, title, children, action }) {
  return <header className="page-heading"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1>{children && <p className="page-lede">{children}</p>}</div>{action}</header>;
}

export function StatusPill({ children, tone = '' }) {
  return <span className={`status-pill ${tone || String(children).toLowerCase().replaceAll('_', '-')}`}>{String(children).replaceAll('_', ' ')}</span>;
}

export function Pagination({ page, pages, onChange }) {
  if (pages <= 1) return null;
  return (
    <nav className="pagination" aria-label="Pagination">
      <button className="button button-quiet" type="button" disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</button>
      <span>Page {page} of {pages}</span>
      <button className="button button-quiet" type="button" disabled={page >= pages} onClick={() => onChange(page + 1)}>Next</button>
    </nav>
  );
}
