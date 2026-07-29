import { apiFetch } from "./client";
import type {
  DocDetailResponse,
  DocListResponse,
  InsertDocReq,
  PageDetailResponse,
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
