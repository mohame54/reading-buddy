import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { deleteDoc, getAdminDoc, realignDoc, realignPage } from "../../api/admin";
import { ApiError } from "../../api/client";
import type { DocDetailResponse } from "../../types/api";
import { AppShell, ErrorBanner, LoadingState, PageLayout } from "../../components/Layout";

export function DocDetail() {
  const { t } = useTranslation();
  const { docId } = useParams<{ docId: string }>();
  const navigate = useNavigate();
  const [doc, setDoc] = useState<DocDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [realigningDoc, setRealigningDoc] = useState(false);
  const [realigningPage, setRealigningPage] = useState<number | null>(null);

  const loadDoc = useCallback(async () => {
    if (!docId) return;
    setLoading(true);
    setError(null);
    try {
      setDoc(await getAdminDoc(docId));
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail ?? err.message : t("admin.loadDocFailed"),
      );
    } finally {
      setLoading(false);
    }
  }, [docId, t]);

  useEffect(() => {
    void loadDoc();
  }, [loadDoc]);

  const handleDelete = async () => {
    if (!docId || !confirm(t("admin.confirmDelete"))) return;
    setDeleting(true);
    try {
      await deleteDoc(docId);
      navigate("/admin");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail ?? err.message : t("admin.deleteFailed"),
      );
      setDeleting(false);
    }
  };

  const handleRealignDoc = async () => {
    if (!docId || !confirm(t("admin.confirmRealign"))) return;
    setRealigningDoc(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await realignDoc(docId);
      const skipped = result.pages_skipped
        ? t("admin.skippedPart", { count: result.pages_skipped })
        : "";
      setSuccess(t("admin.alignedSuccess", { aligned: result.pages_aligned, skipped }));
      await loadDoc();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail ?? err.message : t("admin.realignFailed"),
      );
    } finally {
      setRealigningDoc(false);
    }
  };

  const handleRealignPage = async (pageNumber: number) => {
    if (!docId) return;
    setRealigningPage(pageNumber);
    setError(null);
    setSuccess(null);
    try {
      await realignPage(docId, pageNumber);
      setSuccess(t("admin.pageAligned", { number: pageNumber }));
      await loadDoc();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail ?? err.message : t("admin.realignFailed"),
      );
    } finally {
      setRealigningPage(null);
    }
  };

  const busy = deleting || realigningDoc || realigningPage !== null;

  return (
    <>
      <AppShell />
      <PageLayout
        title={doc?.title ?? t("admin.document")}
        actions={
          <Link to="/admin" className="btn">
            {t("common.backToDashboard")}
          </Link>
        }
      >
        {error && <ErrorBanner message={error} />}
        {success && <p className="hint">{success}</p>}
        {loading ? (
          <LoadingState />
        ) : doc ? (
          <>
            <dl className="meta-list">
              <dt>{t("admin.id")}</dt>
              <dd>{doc.id}</dd>
              <dt>{t("admin.format")}</dt>
              <dd>{doc.ext}</dd>
              <dt>{t("admin.pages")}</dt>
              <dd>{doc.pages_number}</dd>
              {doc.content_url && (
                <>
                  <dt>{t("admin.documentLabel")}</dt>
                  <dd>
                    <a href={doc.content_url} target="_blank" rel="noreferrer">
                      {t("admin.openOriginal")}
                    </a>
                  </dd>
                </>
              )}
            </dl>

            <p style={{ marginBottom: "1.5rem" }}>
              <button
                type="button"
                className="btn"
                onClick={handleRealignDoc}
                disabled={busy}
              >
                {realigningDoc ? t("admin.realigningAll") : t("admin.realignAll")}
              </button>
            </p>

            <h2>{t("admin.pagesHeading")}</h2>
            <div className="page-list">
              {doc.pages.map((page) => {
                const pageHasText =
                  page.has_text ?? Boolean(page.content.split(/\s+/).filter(Boolean).length);
                const canRealign = pageHasText && Boolean(page.audio_url);
                return (
                  <article key={page.id} className="page-preview">
                    <h3>{t("common.page", { number: page.page_number })}</h3>
                    {pageHasText ? (
                      <p className="arabic-text" dir="auto">
                        {page.content}
                      </p>
                    ) : (
                      <p className="hint">{t("admin.noReadingText")}</p>
                    )}
                    {page.audio_url && (
                      <audio controls src={page.audio_url} preload="none" />
                    )}
                    {canRealign && (
                      <p style={{ marginTop: "0.75rem" }}>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => handleRealignPage(page.page_number)}
                          disabled={busy}
                        >
                          {realigningPage === page.page_number
                            ? t("admin.realigning")
                            : t("admin.realignPage")}
                        </button>
                      </p>
                    )}
                  </article>
                );
              })}
            </div>

            <button
              type="button"
              className="btn btn-danger"
              onClick={handleDelete}
              disabled={busy}
            >
              {deleting ? t("admin.deleting") : t("admin.deleteDoc")}
            </button>
          </>
        ) : null}
      </PageLayout>
    </>
  );
}
