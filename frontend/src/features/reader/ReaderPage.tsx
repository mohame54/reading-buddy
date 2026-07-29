import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getDoc } from "../../api/catalog";
import { ApiError } from "../../api/client";
import type { DocDetailResponse, FinalScoreResponse } from "../../types/api";
import { AppShell, ErrorBanner, LoadingState, PageLayout } from "../../components/Layout";
import { prefetchAudio } from "./playWordClip";
import { useReadingSession } from "./useReadingSession";
import { useRecorder } from "./useRecorder";

function ReaderSession({
  docId,
  doc,
  audioMap,
}: {
  docId: string;
  doc: DocDetailResponse;
  audioMap: Map<number, HTMLAudioElement>;
}) {
  const navigate = useNavigate();

  const handleScore = useCallback(
    (score: FinalScoreResponse) => {
      navigate("/users/score", { state: { score, title: doc.title } });
    },
    [navigate, doc.title],
  );

  const {
    phase,
    pageNumber,
    pagesTotal,
    pageText,
    pageImageUrl,
    hasText,
    cursor,
    canGoNext,
    mismatch,
    error: sessionError,
    connected,
    sendAudio,
    goNextPage,
    endSession,
    setPhase,
  } = useReadingSession({
    docId,
    audioMap,
    onScore: handleScore,
  });

  const { recording, error: recorderError, start, stop } = useRecorder();

  const handleRecord = async () => {
    if (recording) {
      const base64 = await stop();
      if (base64) sendAudio(base64);
      else setPhase("idle");
    } else {
      await start();
      setPhase("recording");
    }
  };

  const words = pageText.split(/\s+/).filter(Boolean);
  const progressPercent =
    words.length > 0 ? Math.min(100, (cursor / words.length) * 100) : 0;

  const wordClass = (index: number) => {
    if (mismatch?.index === index) return "word word-wrong";
    if (index < cursor) return "word word-correct";
    return "word word-pending";
  };

  const highlightedWords = words.map((word, i) => (
    <span key={i} className={wordClass(i)}>
      {word}{" "}
    </span>
  ));

  return (
    <>
      {(sessionError || recorderError) && (
        <ErrorBanner message={sessionError ?? recorderError ?? ""} />
      )}

      <div className="reader-meta">
        <span>
          Page {pageNumber} of {pagesTotal}
        </span>
        <span className={connected ? "status-ok" : "status-warn"}>
          {connected ? "Connected" : "Connecting…"}
        </span>
      </div>

      {pageImageUrl ? (
        <img
          src={pageImageUrl}
          alt={`Page ${pageNumber}`}
          className="reader-page-image"
        />
      ) : (
        <p className="hint reader-image-fallback">Page image unavailable</p>
      )}

      <div className="reader-text arabic-text" dir="auto">
        {hasText ? (
          highlightedWords
        ) : (
          <p className="hint">No reading text on this page — continue when ready.</p>
        )}
      </div>

      {hasText && words.length > 0 && (
        <div className="reader-progress" aria-label="Reading progress">
          <div className="reader-progress-track">
            <div
              className="reader-progress-fill"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <span className="reader-progress-label">
            {Math.min(cursor, words.length)} / {words.length} words
          </span>
        </div>
      )}

      {mismatch && (
        <div className="feedback-box">
          <p>
            Expected: <strong>{mismatch.expected}</strong>
            {mismatch.heard && (
              <>
                {" "}
                · Heard: <em>{mismatch.heard}</em>
              </>
            )}
          </p>
          <p className="hint">Listen to the correct pronunciation and try again.</p>
        </div>
      )}

      <div className="reader-controls">
        {hasText && (
          <button
            type="button"
            className={`btn ${recording ? "btn-danger" : "btn-primary"}`}
            onClick={handleRecord}
            disabled={phase === "processing" || !connected}
          >
            {recording ? "Stop" : phase === "retry" ? "Try again" : "Record"}
          </button>
        )}

        <button type="button" className="btn" onClick={goNextPage} disabled={!canGoNext}>
          Next page
        </button>

        <button type="button" className="btn btn-ghost" onClick={endSession}>
          Finish early
        </button>
      </div>

      <p className="phase-label">Status: {phase}</p>
    </>
  );
}

export function ReaderPage() {
  const { docId } = useParams<{ docId: string }>();
  const [doc, setDoc] = useState<DocDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [prepareError, setPrepareError] = useState<string | null>(null);
  const [audioMap, setAudioMap] = useState<Map<number, HTMLAudioElement> | null>(null);

  useEffect(() => {
    if (!docId) return;
    setLoading(true);
    setPrepareError(null);
    setAudioMap(null);

    getDoc(docId)
      .then(async (detail) => {
        setDoc(detail);
        const map = new Map<number, HTMLAudioElement>();
        await Promise.all(
          detail.pages.map(async (page) => {
            if (page.audio_url) {
              try {
                const audio = await prefetchAudio(page.audio_url);
                map.set(page.page_number, audio);
              } catch {
                // Continue without prefetch
              }
            }
          }),
        );
        setAudioMap(map);
      })
      .catch((err) => {
        setPrepareError(
          err instanceof ApiError ? err.detail ?? err.message : "Failed to prepare book",
        );
      })
      .finally(() => setLoading(false));
  }, [docId]);

  if (loading) {
    return (
      <>
        <AppShell />
        <PageLayout title="Preparing book…">
          <LoadingState label="Loading pages and audio…" />
        </PageLayout>
      </>
    );
  }

  if (prepareError || !doc || !audioMap || !docId) {
    return (
      <>
        <AppShell />
        <PageLayout title="Reader">
          <ErrorBanner message={prepareError ?? "Book not found"} />
          <Link to="/users" className="btn">
            Back to library
          </Link>
        </PageLayout>
      </>
    );
  }

  return (
    <>
      <AppShell />
      <PageLayout
        title={doc.title}
        actions={
          <Link to="/users" className="btn">
            Back to library
          </Link>
        }
      >
        <ReaderSession docId={docId} doc={doc} audioMap={audioMap} />
      </PageLayout>
    </>
  );
}
