import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { deleteDoc, getAdminDoc, realignDoc, realignPage } from "../../api/admin";
import { ApiError } from "../../api/client";
import type { DocDetailResponse } from "../../types/api";
import { AppShell, ErrorBanner, LoadingState, PageLayout } from "../../components/Layout";

export function DocDetail() {
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
      setError(err instanceof ApiError ? err.detail ?? err.message : "Failed to load document");
    } finally {
      setLoading(false);
    }
  }, [docId]);

  useEffect(() => {
    void loadDoc();
  }, [loadDoc]);

  const handleDelete = async () => {
    if (!docId || !confirm("Delete this document permanently?")) return;
    setDeleting(true);
    try {
      await deleteDoc(docId);
      navigate("/admin");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail ?? err.message : "Delete failed");
      setDeleting(false);
    }
  };

  const handleRealignDoc = async () => {
    if (!docId || !confirm("Re-run word alignment for all reading pages?")) return;
    setRealigningDoc(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await realignDoc(docId);
      setSuccess(
        `Aligned ${result.pages_aligned} page(s)` +
          (result.pages_skipped ? `, skipped ${result.pages_skipped}` : "") +
          ".",
      );
      await loadDoc();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail ?? err.message : "Re-align failed");
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
      setSuccess(`Page ${pageNumber} alignment updated.`);
      await loadDoc();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail ?? err.message : "Re-align failed");
    } finally {
      setRealigningPage(null);
    }
  };

  const busy = deleting || realigningDoc || realigningPage !== null;

  return (
    <>
      <AppShell />
      <PageLayout
        title={doc?.title ?? "Document"}
        actions={
          <Link to="/admin" className="btn">
            Back to dashboard
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
              <dt>ID</dt>
              <dd>{doc.id}</dd>
              <dt>Format</dt>
              <dd>{doc.ext}</dd>
              <dt>Pages</dt>
              <dd>{doc.pages_number}</dd>
              {doc.content_url && (
                <>
                  <dt>Document</dt>
                  <dd>
                    <a href={doc.content_url} target="_blank" rel="noreferrer">
                      Open original
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
                {realigningDoc ? "Re-aligning all pages…" : "Re-align all pages"}
              </button>
            </p>

            <h2>Pages</h2>
            <div className="page-list">
              {doc.pages.map((page) => {
                const pageHasText =
                  page.has_text ?? Boolean(page.content.split(/\s+/).filter(Boolean).length);
                const canRealign = pageHasText && Boolean(page.audio_url);
                return (
                  <article key={page.id} className="page-preview">
                    <h3>Page {page.page_number}</h3>
                    {pageHasText ? (
                      <p className="arabic-text" dir="auto">
                        {page.content}
                      </p>
                    ) : (
                      <p className="hint">No reading text (picture-only page)</p>
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
                            ? "Re-aligning…"
                            : "Re-align page"}
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
              {deleting ? "Deleting…" : "Delete document"}
            </button>
          </>
        ) : null}
      </PageLayout>
    </>
  );
}
