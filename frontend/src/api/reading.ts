import { apiFetch } from "./client";
import type {
  CheckReadingReq,
  CheckReadingResponse,
  FinalScoreResponse,
} from "../types/api";

export function checkReading(body: CheckReadingReq): Promise<CheckReadingResponse> {
  return apiFetch<CheckReadingResponse>("/reading/check", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function skipReading(body: {
  doc_id: string;
  page_number: number;
  cursor: number;
}): Promise<CheckReadingResponse> {
  return apiFetch<CheckReadingResponse>("/reading/skip", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function finishReading(body: {
  doc_id: string;
  words_total: number;
  words_correct: number;
  pages_completed: number;
  words_skipped?: number;
  words_retried_correct?: number;
}): Promise<FinalScoreResponse> {
  return apiFetch<FinalScoreResponse>("/reading/finish", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
