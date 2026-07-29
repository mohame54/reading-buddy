import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { uploadDoc } from "../../api/admin";
import { ApiError, fileToBase64, getFileExtension } from "../../api/client";
import { AppShell, ErrorBanner, PageLayout } from "../../components/Layout";

interface PageEntry {
  text: string;
  audioFile: File | null;
}

export function UploadWizard() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [docFile, setDocFile] = useState<File | null>(null);
  const [pages, setPages] = useState<PageEntry[]>([{ text: "", audioFile: null }]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addPage = () => setPages((p) => [...p, { text: "", audioFile: null }]);

  const removePage = (index: number) => {
    if (pages.length <= 1) return;
    setPages((p) => p.filter((_, i) => i !== index));
  };

  const updatePage = (index: number, field: keyof PageEntry, value: string | File | null) => {
    setPages((p) => p.map((page, i) => (i === index ? { ...page, [field]: value } : page)));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!docFile) {
      setError("Please select a document file.");
      return;
    }
    if (!title.trim()) {
      setError("Please enter a title.");
      return;
    }
    if (pages.some((p) => !p.text.trim() || !p.audioFile)) {
      setError("Each page needs text and a reference audio file (WAV or MP3).");
      return;
    }

    setSubmitting(true);
    try {
      const content = await fileToBase64(docFile);
      const ext = getFileExtension(docFile.name);
      const pagePayload = await Promise.all(
        pages.map(async (p) => ({
          text: p.text.trim(),
          audio: await fileToBase64(p.audioFile!),
        })),
      );

      const res = await uploadDoc({
        title: title.trim(),
        ext,
        pages_number: pages.length,
        content,
        pages: pagePayload,
      });

      if (res.doc_id) {
        navigate(`/admin/docs/${res.doc_id}`);
      } else {
        navigate("/admin");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail ?? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <AppShell />
      <PageLayout
        title="Upload book"
        actions={
          <Link to="/admin" className="btn">
            Back to dashboard
          </Link>
        }
      >
        {error && <ErrorBanner message={error} />}
        <form className="upload-form" onSubmit={handleSubmit}>
          <label>
            Title
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </label>

          <label>
            Document file (PDF, EPUB, etc.)
            <input
              type="file"
              accept=".pdf,.epub,.doc,.docx"
              onChange={(e) => setDocFile(e.target.files?.[0] ?? null)}
              required
            />
          </label>

          <fieldset className="pages-fieldset">
            <legend>Pages ({pages.length})</legend>
            {pages.map((page, i) => (
              <div key={i} className="page-entry">
                <h3>Page {i + 1}</h3>
                <label>
                  Reading text
                  <textarea
                    value={page.text}
                    onChange={(e) => updatePage(i, "text", e.target.value)}
                    rows={3}
                    dir="auto"
                    required
                  />
                </label>
                <label>
                  Reference audio (WAV or MP3)
                  <input
                    type="file"
                    accept=".wav,.mp3,audio/wav,audio/mpeg"
                    onChange={(e) => updatePage(i, "audioFile", e.target.files?.[0] ?? null)}
                    required
                  />
                </label>
                {pages.length > 1 && (
                  <button type="button" className="btn btn-danger btn-sm" onClick={() => removePage(i)}>
                    Remove page
                  </button>
                )}
              </div>
            ))}
            <button type="button" className="btn" onClick={addPage}>
              Add page
            </button>
          </fieldset>

          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? "Uploading…" : "Upload book"}
          </button>
        </form>
      </PageLayout>
    </>
  );
}
