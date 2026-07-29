import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { listDocs } from "../../api/catalog";
import { ApiError } from "../../api/client";
import type { DocSummary } from "../../types/api";
import {
  AppShell,
  ErrorBanner,
  LoadingState,
  PageLayout,
  Pagination,
} from "../../components/Layout";
import { BookCard } from "./BookCard";

const PAGE_SIZE = 10;

export function LibraryPage() {
  const { t } = useTranslation();
  const [items, setItems] = useState<DocSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    listDocs(offset, PAGE_SIZE)
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((err) => {
        setError(
          err instanceof ApiError ? err.detail ?? err.message : t("library.loadFailed"),
        );
      })
      .finally(() => setLoading(false));
  }, [offset, t]);

  return (
    <>
      <AppShell />
      <PageLayout title={t("library.title")}>
        {error && <ErrorBanner message={error} />}
        {loading ? (
          <LoadingState />
        ) : items.length === 0 ? (
          <p className="empty">{t("library.empty")}</p>
        ) : (
          <>
            <div className="book-grid">
              {items.map((doc) => (
                <BookCard key={doc.id} doc={doc} />
              ))}
            </div>
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
