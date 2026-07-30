import { useCallback, useEffect, useRef, useState } from "react";
import { ReadingSession } from "../../api/websocket";
import i18n from "../../i18n";
import type {
  FinalScoreResponse,
  ReaderPhase,
  WordMismatch,
} from "../../types/api";

interface UseReadingSessionOptions {
  docId: string;
  onScore: (score: FinalScoreResponse) => void;
}

export function useReadingSession({ docId, onScore }: UseReadingSessionOptions) {
  const sessionRef = useRef<ReadingSession | null>(null);
  const onScoreRef = useRef(onScore);
  const pageNumberRef = useRef(1);

  const [phase, setPhase] = useState<ReaderPhase>("idle");
  const [pageNumber, setPageNumber] = useState(1);
  const [pagesTotal, setPagesTotal] = useState(1);
  const [pageText, setPageText] = useState("");
  const [pageImageUrl, setPageImageUrl] = useState<string | null>(null);
  const [hasText, setHasText] = useState(true);
  const [cursor, setCursor] = useState(0);
  const [canGoNext, setCanGoNext] = useState(false);
  const [mismatch, setMismatch] = useState<WordMismatch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    onScoreRef.current = onScore;
  }, [onScore]);

  useEffect(() => {
    const session = new ReadingSession({
      onOpen: () => setConnected(true),
      onPage: (msg) => {
        setPageText(msg.content);
        setPageImageUrl(msg.image_url ?? null);
        setPageNumber(msg.page_number);
        pageNumberRef.current = msg.page_number;
        setPagesTotal(msg.pages_total);
        const pageHasText =
          msg.has_text ?? Boolean(msg.content.split(/\s+/).filter(Boolean).length);
        setHasText(pageHasText);
        setCursor(0);
        setCanGoNext(false);
        setMismatch(null);
        setPhase("idle");
      },
      onOk: (msg) => {
        setCursor(msg.cursor);
        setMismatch(null);
        setPhase("idle");
      },
      onFeedback: (msg) => {
        const m = msg.mismatches[0] ?? null;
        setMismatch(m);
        setCursor(msg.cursor);
        setPhase("retry");
      },
      onPageComplete: (msg) => {
        setCursor(msg.cursor);
        setCanGoNext(true);
        setPhase("page_done");
      },
      onScore: (msg) => {
        setPhase("book_done");
        onScoreRef.current(msg);
        session.close();
      },
      onError: (message) => {
        setError(message);
        setPhase("idle");
      },
      onClose: () => setConnected(false),
    });

    sessionRef.current = session;

    session
      .connect()
      .then(() => session.start(docId, 1))
      .catch((err) =>
        setError(
          err instanceof Error ? err.message : i18n.t("reader.connectionFailed"),
        ),
      );

    return () => {
      session.close();
    };
  }, [docId]);

  const sendAudio = useCallback((base64: string) => {
    setPhase("processing");
    setError(null);
    sessionRef.current?.sendAudio(base64);
  }, []);

  const goNextPage = useCallback(() => {
    setCanGoNext(false);
    setMismatch(null);
    setPhase("idle");
    sessionRef.current?.nextPage();
  }, []);

  const endSession = useCallback(() => {
    sessionRef.current?.end();
  }, []);

  const skipWord = useCallback(() => {
    setPhase("processing");
    setError(null);
    sessionRef.current?.skip();
  }, []);

  return {
    phase,
    pageNumber,
    pagesTotal,
    pageText,
    pageImageUrl,
    hasText,
    cursor,
    canGoNext,
    mismatch,
    error,
    connected,
    sendAudio,
    goNextPage,
    endSession,
    skipWord,
    setPhase,
  };
}
