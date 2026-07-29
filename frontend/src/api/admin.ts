import { apiFetch } from "./client";
import type {
  DocDetailResponse,
  DocListResponse,
  InsertDocReq,
  PageDetailResponse,
  RealignDocResponse,
  StatusResponse,
} from "../types/api";

export function listAdminDocs(offset: number, limit: number): Promise<DocListResponse> {
  return apiFetch<DocListResponse>(`/admin/docs/${offset}/${limit}`);
}

export function getAdminDoc(docId: string): Promise<DocDetailResponse> {
  return apiFetch<DocDetailResponse>(`/admin/docs/${docId}`);
}

export function getAdminPage(
  docId: string,
  pageNumber: number,
): Promise<PageDetailResponse> {
  return apiFetch<PageDetailResponse>(`/admin/docs/${docId}/pages/${pageNumber}`);
}

export function uploadDoc(body: InsertDocReq): Promise<StatusResponse> {
  return apiFetch<StatusResponse>("/admin/docs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteDoc(docId: string): Promise<StatusResponse> {
  return apiFetch<StatusResponse>(`/admin/docs/${docId}`, {
    method: "DELETE",
  });
}

export function realignDoc(docId: string): Promise<RealignDocResponse> {
  return apiFetch<RealignDocResponse>(`/admin/docs/${docId}/realign`, {
    method: "POST",
  });
}

export function realignPage(
  docId: string,
  pageNumber: number,
): Promise<PageDetailResponse> {
  return apiFetch<PageDetailResponse>(
    `/admin/docs/${docId}/pages/${pageNumber}/realign`,
    { method: "POST" },
  );
}
