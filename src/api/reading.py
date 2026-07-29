import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from src.api.deps import get_stt_service
from src.data.reqs import (
    CheckReadingReq,
    CheckReadingResponse,
    FinalScoreResponse,
    FinishReadingReq,
)
from src.services.reading_session import ReadingSession
from src.services.stt_service import STTService
from src.utils.compare import tokenize_text
from src.utils.decorators import Timer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reading", tags=["reading"])


@router.post("/check", response_model=CheckReadingResponse)
async def check_reading(
    req: CheckReadingReq, stt: STTService = Depends(get_stt_service)
):
    try:
        return await stt.check_reading(
            req.doc_id, req.page_number, req.audio, req.cursor
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/finish", response_model=FinalScoreResponse)
async def finish_reading(
    req: FinishReadingReq, stt: STTService = Depends(get_stt_service)
):
    doc = await stt.get_doc(req.doc_id, include_url=False)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return stt.build_final_score(
        req.doc_id,
        req.words_total,
        req.words_correct,
        req.pages_completed,
        doc.pages_number,
    )


@router.websocket("/session")
async def reading_session(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket reading session connected")
    stt: STTService = websocket.app.state.stt_service
    session: ReadingSession | None = None

    async def send(payload: Dict[str, Any]) -> None:
        await websocket.send_text(json.dumps(payload))

    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)
            msg_type = message.get("type")

            if msg_type == "start":
                doc_id = message["doc_id"]
                page_number = int(message.get("page_number", 1))
                start_extra = {"doc_id": doc_id, "page": page_number}
                with Timer("WebSocket session start", logger=logger, extra=start_extra):
                    doc = await stt.get_doc(doc_id, include_url=False)
                    if not doc:
                        await send({"type": "error", "message": "Document not found"})
                        continue
                    page = await stt.get_page(doc_id, page_number, include_url=False)
                    if not page:
                        await send({"type": "error", "message": "Page not found"})
                        continue
                    session = ReadingSession(
                        doc_id=doc_id,
                        page_number=page_number,
                        pages_total=doc.pages_number,
                    )
                    session.reset_page(page_number, len(tokenize_text(page.content)))
                    start_extra["pages_total"] = doc.pages_number
                    await send(
                        {
                            "type": "page",
                            "doc_id": doc_id,
                            "page_number": page_number,
                            "content": page.content,
                            "pages_total": doc.pages_number,
                        }
                    )
                continue

            if session is None:
                await send({"type": "error", "message": "Session not started"})
                continue

            if msg_type == "audio":
                audio_extra = {
                    "doc_id": session.doc_id,
                    "page": session.page_number,
                    "cursor": session.cursor,
                }
                with Timer("WebSocket audio check", logger=logger, extra=audio_extra):
                    previous_cursor = session.cursor
                    result = await stt.check_reading(
                        session.doc_id,
                        session.page_number,
                        message["data"],
                        session.cursor,
                    )
                    session.apply_check(
                        previous_cursor, result.cursor, result.page_complete
                    )
                    if result.mismatches:
                        outcome = "feedback"
                        await send(
                            {
                                "type": "feedback",
                                "mismatches": [m.model_dump() for m in result.mismatches],
                                "cursor": result.cursor,
                            }
                        )
                    elif result.page_complete:
                        if session.page_number >= session.pages_total:
                            outcome = "score"
                            score = session.to_score()
                            await send({"type": "score", **score.model_dump()})
                        else:
                            outcome = "page_complete"
                            await send(
                                {
                                    "type": "page_complete",
                                    "page_number": session.page_number,
                                    "cursor": result.cursor,
                                }
                            )
                    else:
                        outcome = "ok"
                        await send({"type": "ok", "cursor": result.cursor})
                    audio_extra["outcome"] = outcome
                    audio_extra["new_cursor"] = result.cursor
                continue

            if msg_type == "next_page":
                next_extra = {
                    "doc_id": session.doc_id,
                    "from_page": session.page_number,
                }
                with Timer("WebSocket next page", logger=logger, extra=next_extra):
                    if session.page_number >= session.pages_total:
                        next_extra["outcome"] = "score"
                        score = session.to_score()
                        await send({"type": "score", **score.model_dump()})
                        continue
                    session.page_number += 1
                    next_extra["to_page"] = session.page_number
                    page = await stt.get_page(
                        session.doc_id, session.page_number, include_url=False
                    )
                    if not page:
                        await send({"type": "error", "message": "Page not found"})
                        continue
                    session.reset_page(
                        session.page_number, len(tokenize_text(page.content))
                    )
                    next_extra["outcome"] = "page"
                    await send(
                        {
                            "type": "page",
                            "doc_id": session.doc_id,
                            "page_number": session.page_number,
                            "content": page.content,
                            "pages_total": session.pages_total,
                        }
                    )
                continue

            if msg_type == "end":
                end_extra = {
                    "doc_id": session.doc_id,
                    "page": session.page_number,
                }
                with Timer("WebSocket session end", logger=logger, extra=end_extra):
                    score = session.to_score()
                    end_extra["words_total"] = score.words_total
                    end_extra["accuracy"] = score.accuracy
                    await send({"type": "score", **score.model_dump()})
                break

            await send({"type": "error", "message": f"Unknown message type: {msg_type}"})

    except WebSocketDisconnect:
        logger.info(
            "WebSocket reading session disconnected doc_id=%s",
            session.doc_id if session else None,
        )
        return
    except Exception as exc:
        logger.exception(
            "WebSocket reading session error doc_id=%s",
            session.doc_id if session else None,
        )
        try:
            await send({"type": "error", "message": str(exc)})
        except Exception:
            pass
