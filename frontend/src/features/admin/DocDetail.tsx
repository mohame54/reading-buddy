import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { deleteDoc, getAdminDoc } from "../../api/admin";
import { ApiError } from "../../api/client";
import type { DocDetailResponse } from "../../types/api";
import { AppShell, ErrorBanner, LoadingState, PageLayout } from "../../components/Layout";

export function DocDetail() {
  const { docId } = useParams<{ docId: string }>();
  const navigate = useNavigate();
  const [doc, setDoc] = useState<DocDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!docId) return;
    setLoading(true);
    getAdminDoc(docId)
      .then(setDoc)
      .catch((err) => {
        setError(err instanceof ApiError ? err.detail ?? err.message : "Failed to load document");
      })
      .finally(() => setLoading(false));
  }, [docId]);

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

            <h2>Pages</h2>
            <div className="page-list">
              {doc.pages.map((page) => {
                const pageHasText =
                  page.has_text ?? Boolean(page.content.split(/\s+/).filter(Boolean).length);
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
                  </article>
                );
              })}
            </div>

            <button
              type="button"
              className="btn btn-danger"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? "Deleting…" : "Delete document"}
            </button>
          </>
        ) : null}
      </PageLayout>
    </>
  );
}
