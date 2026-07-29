import { useCallback, useEffect, useRef, useState } from "react";
import { ReadingSession } from "../../api/websocket";
import type {
  FinalScoreResponse,
  ReaderPhase,
  WordMismatch,
} from "../../types/api";
import { playWordClip } from "./playWordClip";

interface UseReadingSessionOptions {
  docId: string;
  audioMap: Map<number, HTMLAudioElement>;
  onScore: (score: FinalScoreResponse) => void;
}

export function useReadingSession({ docId, audioMap, onScore }: UseReadingSessionOptions) {
  const sessionRef = useRef<ReadingSession | null>(null);
  const audioMapRef = useRef(audioMap);
  const onScoreRef = useRef(onScore);
  const pageNumberRef = useRef(1);

  const [phase, setPhase] = useState<ReaderPhase>("idle");
  const [pageNumber, setPageNumber] = useState(1);
  const [pagesTotal, setPagesTotal] = useState(1);
  const [pageText, setPageText] = useState("");
  const [hasText, setHasText] = useState(true);
  const [cursor, setCursor] = useState(0);
  const [canGoNext, setCanGoNext] = useState(false);
  const [mismatch, setMismatch] = useState<WordMismatch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    audioMapRef.current = audioMap;
  }, [audioMap]);

  useEffect(() => {
    onScoreRef.current = onScore;
  }, [onScore]);

  useEffect(() => {
    const session = new ReadingSession({
      onOpen: () => setConnected(true),
      onPage: (msg) => {
        setPageText(msg.content);
        setPageNumber(msg.page_number);
        pageNumberRef.current = msg.page_number;
        setPagesTotal(msg.pages_total);
        const pageHasText =
          msg.has_text ?? Boolean(msg.content.split(/\s+/).filter(Boolean).length);
        setHasText(pageHasText);
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
        if (m?.start != null && m?.end != null) {
          const audio = audioMapRef.current.get(pageNumberRef.current);
          if (audio) playWordClip(audio, m.start, m.end);
        }
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
      .catch((err) => setError(err instanceof Error ? err.message : "Connection failed"));

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

  return {
    phase,
    pageNumber,
    pagesTotal,
    pageText,
    hasText,
    cursor,
    canGoNext,
    mismatch,
    error,
    connected,
    sendAudio,
    goNextPage,
    endSession,
    setPhase,
  };
}
