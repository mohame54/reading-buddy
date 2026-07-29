import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { uploadDoc } from "../../api/admin";
import { ApiError, fileToBase64, getFileExtension } from "../../api/client";
import { AppShell, ErrorBanner, PageLayout } from "../../components/Layout";

interface PageEntry {
  text: string;
  audioFile: File | null;
}

export function UploadWizard() {
  const { t } = useTranslation();
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
      setError(t("upload.needFile"));
      return;
    }
    if (!title.trim()) {
      setError(t("upload.needTitle"));
      return;
    }

    const missingAudio = pages.findIndex((p) => p.text.trim() && !p.audioFile);
    if (missingAudio >= 0) {
      setError(t("upload.needAudio", { number: missingAudio + 1 }));
      return;
    }

    setSubmitting(true);
    try {
      const content = await fileToBase64(docFile);
      const ext = getFileExtension(docFile.name);
      const pagePayload = await Promise.all(
        pages.map(async (p) => {
          const text = p.text.trim();
          if (!text) {
            return { text: "", audio: null };
          }
          return {
            text,
            audio: await fileToBase64(p.audioFile!),
          };
        }),
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
      setError(err instanceof ApiError ? err.detail ?? err.message : t("upload.failed"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <AppShell />
      <PageLayout
        title={t("upload.title")}
        actions={
          <Link to="/admin" className="btn">
            {t("common.backToDashboard")}
          </Link>
        }
      >
        {error && <ErrorBanner message={error} />}
        <form className="upload-form" onSubmit={handleSubmit}>
          <label>
            {t("upload.fieldTitle")}
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </label>

          <label>
            {t("upload.fieldDoc")}
            <input
              type="file"
              accept=".pdf,.epub,.doc,.docx"
              onChange={(e) => setDocFile(e.target.files?.[0] ?? null)}
              required
            />
          </label>

          <fieldset className="pages-fieldset">
            <legend>{t("upload.pagesLegend", { count: pages.length })}</legend>
            <p className="hint">{t("upload.pagesHint")}</p>
            {pages.map((page, i) => {
              const hasText = Boolean(page.text.trim());
              return (
                <div key={i} className="page-entry">
                  <h3>{t("common.page", { number: i + 1 })}</h3>
                  <label>
                    {t("upload.readingText")}
                    <textarea
                      value={page.text}
                      onChange={(e) => updatePage(i, "text", e.target.value)}
                      rows={3}
                      dir="auto"
                      placeholder={t("upload.textPlaceholder")}
                    />
                  </label>
                  <label>
                    {t("upload.refAudio")}
                    {hasText ? "" : t("upload.optional")}
                    <input
                      type="file"
                      accept=".wav,.mp3,audio/wav,audio/mpeg"
                      onChange={(e) => updatePage(i, "audioFile", e.target.files?.[0] ?? null)}
                      required={hasText}
                    />
                  </label>
                  {pages.length > 1 && (
                    <button
                      type="button"
                      className="btn btn-danger btn-sm"
                      onClick={() => removePage(i)}
                    >
                      {t("upload.removePage")}
                    </button>
                  )}
                </div>
              );
            })}
            <button type="button" className="btn" onClick={addPage}>
              {t("upload.addPage")}
            </button>
          </fieldset>

          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? t("upload.submitting") : t("upload.submit")}
          </button>
        </form>
      </PageLayout>
    </>
  );
}
