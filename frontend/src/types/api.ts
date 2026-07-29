// Shared
export interface DocListResponse {
  items: DocSummary[];
  total: number;
  offset: number;
  limit: number;
}

export interface DocSummary {
  id: string;
  title: string;
  ext: string;
  pages_number: number;
  first_page_content: string | null;
  first_page_image_url: string | null;
}

export interface DocDetailResponse {
  id: string;
  title: string;
  ext: string;
  pages_number: number;
  gcs_uri: string;
  content_url: string | null;
  pages: PageSummary[];
}

export interface PageSummary {
  id: string;
  page_number: number;
  content: string;
  audio_url: string | null;
  image_url?: string | null;
  has_text?: boolean;
}

export interface PageDetailResponse {
  id: string;
  doc_id: string;
  page_number: number;
  content: string;
  content_aligned: string | null;
  audio_gcs_uri: string;
  audio_url: string | null;
  image_url?: string | null;
  has_text?: boolean;
}

export interface StatusResponse {
  status: "success" | "error";
  message: string | null;
  doc_id: string | null;
}

export interface RealignDocResponse {
  doc_id: string;
  pages_aligned: number;
  pages_skipped: number;
}

// Admin upload
export interface InsertDocReq {
  title: string;
  ext: string;
  pages_number: number;
  content: string;
  pages: {
    text: string;
    audio?: string | null;
  }[];
}

// Reading
export interface CheckReadingReq {
  doc_id: string;
  page_number: number;
  audio: string;
  cursor: number;
}

export interface WordMismatch {
  index: number;
  expected: string;
  heard: string | null;
  start: number | null;
  end: number | null;
}

export interface CheckReadingResponse {
  ok: boolean;
  cursor: number;
  page_complete: boolean;
  mismatches: WordMismatch[];
}

export interface FinalScoreResponse {
  doc_id: string;
  words_total: number;
  words_correct: number;
  pages_completed: number;
  pages_total: number;
  accuracy: number;
}

// WebSocket messages
export type ClientMessage =
  | { type: "start"; doc_id: string; page_number?: number }
  | { type: "audio"; data: string }
  | { type: "next_page" }
  | { type: "end" };

export type ServerMessage =
  | {
      type: "page";
      doc_id: string;
      page_number: number;
      content: string;
      image_url?: string | null;
      pages_total: number;
      has_text?: boolean;
    }
  | { type: "ok"; cursor: number }
  | { type: "feedback"; mismatches: WordMismatch[]; cursor: number }
  | { type: "page_complete"; page_number: number; cursor: number }
  | ({ type: "score" } & FinalScoreResponse)
  | { type: "error"; message: string };

export type ReaderPhase =
  | "idle"
  | "recording"
  | "processing"
  | "retry"
  | "page_done"
  | "book_done";
