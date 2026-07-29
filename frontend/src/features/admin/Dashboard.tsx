import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
        setError(
          err instanceof ApiError ? err.detail ?? err.message : t("admin.loadFailed"),
        );
      })
      .finally(() => setLoading(false));
  }, [offset, t]);

  return (
    <>
      <AppShell />
      <PageLayout
        title={t("admin.dashboard")}
        actions={
          <Link to="/admin/upload" className="btn btn-primary">
            {t("admin.uploadBook")}
          </Link>
        }
      >
        {error && <ErrorBanner message={error} />}
        {loading ? (
          <LoadingState />
        ) : items.length === 0 ? (
          <p className="empty">{t("admin.empty")}</p>
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("admin.colTitle")}</th>
                  <th>{t("admin.colFormat")}</th>
                  <th>{t("admin.colPages")}</th>
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
                        {t("admin.view")}
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
