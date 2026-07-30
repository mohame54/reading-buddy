import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getDoc } from "../../api/catalog";
import { ApiError } from "../../api/client";
import type { DocDetailResponse, FinalScoreResponse } from "../../types/api";
import { AppShell, ErrorBanner, LoadingState, PageLayout } from "../../components/Layout";
import {
  playFullPage,
  playMismatchClip,
  prefetchAudio,
  stopActiveClip,
} from "./playWordClip";
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
  const { t } = useTranslation();
  const navigate = useNavigate();
  const audioMapRef = useRef(audioMap);
  const [pageAudioPlaying, setPageAudioPlaying] = useState(false);
  const [audioLoadError, setAudioLoadError] = useState<string | null>(null);

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
    skipWord,
    setPhase,
  } = useReadingSession({
    docId,
    onScore: handleScore,
  });

  const pageAudioUrl =
    doc.pages.find((page) => page.page_number === pageNumber)?.audio_url ?? null;
  const hasPageAudio = Boolean(pageAudioUrl);

  useEffect(() => {
    audioMapRef.current = audioMap;
  }, [audioMap]);

  const ensurePageAudio = useCallback(async () => {
    if (!pageAudioUrl) return null;

    const cached = audioMapRef.current.get(pageNumber);
    if (cached) return cached;

    try {
      const audio = await prefetchAudio(pageAudioUrl);
      audioMapRef.current.set(pageNumber, audio);
      setAudioLoadError(null);
      return audio;
    } catch {
      setAudioLoadError(t("reader.audioLoadFailed"));
      return null;
    }
  }, [pageAudioUrl, pageNumber, t]);

  const handlePlayPageAudio = useCallback(async () => {
    const audio = await ensurePageAudio();
    if (!audio) return;

    if (!audio.paused) {
      stopActiveClip();
      audio.pause();
      setPageAudioPlaying(false);
      return;
    }

    const played = await playFullPage(audio);
    if (played) {
      setPageAudioPlaying(true);
      audio.onended = () => setPageAudioPlaying(false);
    }
  }, [ensurePageAudio]);

  const handlePlayMismatchWord = useCallback(async () => {
    if (!mismatch) return;
    const audio = await ensurePageAudio();
    if (!audio) return;
    if (mismatch.start != null && mismatch.end != null) {
      await playMismatchClip(audio, mismatch);
    }
  }, [ensurePageAudio, mismatch]);

  const handlePlayMismatchFullPage = useCallback(async () => {
    const audio = await ensurePageAudio();
    if (!audio) return;
    const played = await playFullPage(audio);
    if (played) {
      setPageAudioPlaying(true);
      audio.onended = () => setPageAudioPlaying(false);
    }
  }, [ensurePageAudio]);

  const canPlayWordClip =
    mismatch?.start != null && mismatch?.end != null;

  useEffect(() => {
    setPageAudioPlaying(false);
    setAudioLoadError(null);
  }, [pageNumber]);

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

  const phaseLabel = t(`reader.phases.${phase}`, { defaultValue: phase });

  return (
    <>
      {(sessionError || recorderError) && (
        <ErrorBanner message={sessionError ?? recorderError ?? ""} />
      )}

      <div className="reader-meta">
        <span>
          {t("reader.pageOf", { current: pageNumber, total: pagesTotal })}
        </span>
        <span className={connected ? "status-ok" : "status-warn"}>
          {connected ? t("reader.connected") : t("reader.connecting")}
        </span>
      </div>

      {pageImageUrl ? (
        <img
          src={pageImageUrl}
          alt={t("reader.pageImageAlt", { number: pageNumber })}
          className="reader-page-image"
        />
      ) : (
        <p className="hint reader-image-fallback">{t("reader.pageImageUnavailable")}</p>
      )}

      {hasPageAudio && (
        <div className="reader-audio-bar">
          <button
            type="button"
            className="btn"
            onClick={handlePlayPageAudio}
          >
            {pageAudioPlaying ? t("reader.stopNarration") : t("reader.listenPage")}
          </button>
          {audioLoadError && <p className="hint reader-audio-error">{audioLoadError}</p>}
        </div>
      )}

      <div className="reader-text arabic-text" dir="auto">
        {hasText ? (
          highlightedWords
        ) : (
          <p className="hint">{t("reader.noText")}</p>
        )}
      </div>

      {hasText && words.length > 0 && (
        <div className="reader-progress" aria-label={t("reader.progress")}>
          <div className="reader-progress-track">
            <div
              className="reader-progress-fill"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <span className="reader-progress-label">
            {t("reader.wordsProgress", {
              current: Math.min(cursor, words.length),
              total: words.length,
            })}
          </span>
        </div>
      )}

      {mismatch && (
        <div className="feedback-box">
          <p>
            {t("reader.expected")} <strong>{mismatch.expected}</strong>
            {mismatch.heard && (
              <>
                {" "}
                · {t("reader.heard")} <em>{mismatch.heard}</em>
              </>
            )}
          </p>
          <p className="hint">{t("reader.mismatchHint")}</p>
          {hasPageAudio && (
            <div className="feedback-actions">
              {canPlayWordClip && (
                <button
                  type="button"
                  className="btn feedback-listen-btn"
                  onClick={handlePlayMismatchWord}
                >
                  {t("reader.hearWord")}
                </button>
              )}
              <button
                type="button"
                className={`btn ${canPlayWordClip ? "btn-ghost" : ""} feedback-listen-btn`}
                onClick={handlePlayMismatchFullPage}
              >
                {t("reader.hearFullPage")}
              </button>
            </div>
          )}
          {hasPageAudio && !canPlayWordClip && (
            <p className="hint">{t("reader.wordClipUnavailable")}</p>
          )}
          <div className="feedback-actions">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={skipWord}
              disabled={phase === "processing" || !connected || recording}
            >
              {t("reader.continue")}
            </button>
          </div>
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
            {recording
              ? t("reader.stop")
              : phase === "retry"
                ? t("reader.tryAgain")
                : t("reader.record")}
          </button>
        )}

        <button type="button" className="btn" onClick={goNextPage} disabled={!canGoNext}>
          {t("reader.nextPage")}
        </button>

        <button type="button" className="btn btn-ghost" onClick={endSession}>
          {t("reader.finishEarly")}
        </button>
      </div>

      <p className="phase-label">{t("reader.status", { phase: phaseLabel })}</p>
    </>
  );
}

export function ReaderPage() {
  const { t } = useTranslation();
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
          err instanceof ApiError
            ? err.detail ?? err.message
            : t("reader.prepareFailed"),
        );
      })
      .finally(() => setLoading(false));
  }, [docId, t]);

  if (loading) {
    return (
      <>
        <AppShell />
        <PageLayout title={t("reader.preparing")}>
          <LoadingState label={t("reader.loadingPages")} />
        </PageLayout>
      </>
    );
  }

  if (prepareError || !doc || !audioMap || !docId) {
    return (
      <>
        <AppShell />
        <PageLayout title={t("reader.title")}>
          <ErrorBanner message={prepareError ?? t("reader.notFound")} />
          <Link to="/users" className="btn">
            {t("common.backToLibrary")}
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
            {t("common.backToLibrary")}
          </Link>
        }
      >
        <ReaderSession docId={docId} doc={doc} audioMap={audioMap} />
      </PageLayout>
    </>
  );
}
