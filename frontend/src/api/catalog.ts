import { apiFetch } from "./client";
import type { DocDetailResponse, DocListResponse, PageDetailResponse } from "../types/api";

export function listDocs(offset: number, limit: number): Promise<DocListResponse> {
  return apiFetch<DocListResponse>(`/docs/${offset}/${limit}`);
}

export function getDoc(docId: string): Promise<DocDetailResponse> {
  return apiFetch<DocDetailResponse>(`/docs/${docId}`);
}

export function getPage(docId: string, pageNumber: number): Promise<PageDetailResponse> {
  return apiFetch<PageDetailResponse>(`/docs/${docId}/pages/${pageNumber}`);
}
