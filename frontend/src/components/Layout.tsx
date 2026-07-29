import { Link } from "react-router-dom";

export function AppShell() {
  return (
    <header className="app-header">
      <Link to="/" className="brand">
        Reading Buddy
      </Link>
      <nav className="mode-nav">
        <Link to="/admin">Admin</Link>
        <Link to="/users">Users</Link>
      </nav>
    </header>
  );
}

export function PageLayout({
  title,
  children,
  actions,
}: {
  title: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="page">
      <div className="page-header">
        <h1>{title}</h1>
        {actions && <div className="page-actions">{actions}</div>}
      </div>
      {children}
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return <div className="error-banner">{message}</div>;
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return <div className="loading">{label}</div>;
}

export function Pagination({
  offset,
  limit,
  total,
  onPageChange,
}: {
  offset: number;
  limit: number;
  total: number;
  onPageChange: (newOffset: number) => void;
}) {
  const currentPage = Math.floor(offset / limit) + 1;
  const pageCount = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="pagination">
      <button
        type="button"
        disabled={offset === 0}
        onClick={() => onPageChange(Math.max(0, offset - limit))}
      >
        Previous
      </button>
      <span>
        Page {currentPage} of {pageCount} ({total} total)
      </span>
      <button
        type="button"
        disabled={offset + limit >= total}
        onClick={() => onPageChange(offset + limit)}
      >
        Next
      </button>
    </div>
  );
}
