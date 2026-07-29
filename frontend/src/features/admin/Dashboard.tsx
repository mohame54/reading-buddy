import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAdminDocs } from "../../api/admin";
import { ApiError } from "../../api/client";
import type { DocSummary } from "../../types/api";
import {
  AppShell,
  ErrorBanner,
  LoadingState,
  PageLayout,
  Pagination,
} from "../../components/Layout";

const PAGE_SIZE = 10;

export function Dashboard() {
  const [items, setItems] = useState<DocSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    listAdminDocs(offset, PAGE_SIZE)
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.detail ?? err.message : "Failed to load documents");
      })
      .finally(() => setLoading(false));
  }, [offset]);

  return (
    <>
      <AppShell />
      <PageLayout
        title="Admin Dashboard"
        actions={
          <Link to="/admin/upload" className="btn btn-primary">
            Upload book
          </Link>
        }
      >
        {error && <ErrorBanner message={error} />}
        {loading ? (
          <LoadingState />
        ) : items.length === 0 ? (
          <p className="empty">No documents yet. Upload your first book.</p>
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Format</th>
                  <th>Pages</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((doc) => (
                  <tr key={doc.id}>
                    <td>{doc.title}</td>
                    <td>{doc.ext}</td>
                    <td>{doc.pages_number}</td>
                    <td>
                      <Link to={`/admin/docs/${doc.id}`} className="btn btn-sm">
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination
              offset={offset}
              limit={PAGE_SIZE}
              total={total}
              onPageChange={setOffset}
            />
          </>
        )}
      </PageLayout>
    </>
  );
}
