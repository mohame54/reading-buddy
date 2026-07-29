import { getWsBase } from "./client";
import type { ClientMessage, FinalScoreResponse, ServerMessage } from "../types/api";

export type ReadingSessionHandlers = {
  onPage?: (msg: Extract<ServerMessage, { type: "page" }>) => void;
  onOk?: (msg: Extract<ServerMessage, { type: "ok" }>) => void;
  onFeedback?: (msg: Extract<ServerMessage, { type: "feedback" }>) => void;
  onPageComplete?: (msg: Extract<ServerMessage, { type: "page_complete" }>) => void;
  onScore?: (msg: FinalScoreResponse) => void;
  onError?: (message: string) => void;
  onClose?: () => void;
  onOpen?: () => void;
};

export class ReadingSession {
  private ws: WebSocket | null = null;
  private handlers: ReadingSessionHandlers;

  constructor(handlers: ReadingSessionHandlers) {
    this.handlers = handlers;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const url = `${getWsBase()}/reading/session`;
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.handlers.onOpen?.();
        resolve();
      };

      this.ws.onmessage = (ev) => {
        const msg: ServerMessage = JSON.parse(ev.data);
        switch (msg.type) {
          case "page":
            this.handlers.onPage?.(msg);
            break;
          case "ok":
            this.handlers.onOk?.(msg);
            break;
          case "feedback":
            this.handlers.onFeedback?.(msg);
            break;
          case "page_complete":
            this.handlers.onPageComplete?.(msg);
            break;
          case "score":
            this.handlers.onScore?.(msg);
            break;
          case "error":
            this.handlers.onError?.(msg.message);
            break;
        }
      };

      this.ws.onerror = () => {
        reject(new Error("WebSocket connection failed"));
      };

      this.ws.onclose = () => {
        this.handlers.onClose?.();
      };
    });
  }

  private send(msg: ClientMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket is not connected");
    }
    this.ws.send(JSON.stringify(msg));
  }

  start(docId: string, pageNumber = 1): void {
    this.send({ type: "start", doc_id: docId, page_number: pageNumber });
  }

  sendAudio(base64Wav: string): void {
    this.send({ type: "audio", data: base64Wav });
  }

  nextPage(): void {
    this.send({ type: "next_page" });
  }

  end(): void {
    this.send({ type: "end" });
  }

  close(): void {
    this.ws?.close();
    this.ws = null;
  }
}
