import base64
import io
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

import numpy as np
import soundfile as sf

from src.config import get_settings
from src.bq.base import BigQueryIndexBase
from src.bq.queries import (
    DOC_DELETE_BY_ID,
    DOC_SELECT_BY_ID,
    DOCS_COUNT,
    DOCS_SELECT_ALL,
    PAGE_SELECT,
    PAGE_UPDATE_CONTENT_ALIGNED,
    PAGE_UPDATE_IMAGE_GCS_URI,
    PAGES_DELETE_BY_DOC,
    PAGES_SELECT_BY_DOC,
    PAGES_SELECT_FIRST,
)
from src.data.models import Doc, Page
from src.data.reqs import (
    CheckReadingResponse,
    DocDetailResponse,
    DocListResponse,
    DocSummary,
    FinalScoreResponse,
    InsertDocReq,
    PageDetailResponse,
    PageSummary,
    RealignDocResponse,
    StatusResponse,
    WordMismatch,
)
from src.services.storage_service import StorageService
from src.utils.compare import (
    compare_utterance,
    decode_audio_base64,
    fuzzy_match_segment_index,
    page_has_text,
    parse_content_aligned,
    serialize_content_aligned,
    tokenize_text,
)
from src.utils.decorators import Timer
from src.utils.models import (
    load_stt_recognizer,
    recognize_audio,
    recognize_audios,
    resample_audio,
)
from src.utils.preview import render_first_page_preview, render_page_preview

logger = logging.getLogger(__name__)


class STTService:
    def __init__(
        self,
        model_dir: str,
        storage: StorageService,
        num_threads: int = 2,
        align_batch_size: int = get_settings().stt_align_batch_size,
        schema_path: Optional[str] = None,
    ):
        self.model_dir = model_dir
        self.num_threads = num_threads
        self.align_batch_size = max(1, align_batch_size)
        self.storage = storage
        if schema_path is None:
            schema_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "schemas.json"
            )
        self.schema_path = schema_path
        self.load_components(schema_path)

    def load_components(self, schema_path: str) -> None:
        project_dataset_id = os.getenv("PROJECT_ID")
        if not project_dataset_id:
            raise ValueError("PROJECT_ID environment variable is not set")

        with Timer("Load STT service components", logger=logger):
            self.recognizer = load_stt_recognizer(self.model_dir, self.num_threads)
            self.docs_bq = BigQueryIndexBase(
                proj_dataset_id=project_dataset_id,
                schema_path=schema_path,
                schema_key="docs",
                skip_vertex_init=True,
            )
            self.pages_bq = BigQueryIndexBase(
                proj_dataset_id=project_dataset_id,
                schema_path=schema_path,
                schema_key="pages",
                skip_vertex_init=True,
            )
            self.docs_bq.set_current_table("docs")
            self.pages_bq.set_current_table("pages")

    def start(self) -> None:
        with Timer("Start STT service pool", logger=logger):
            self.docs_bq.start_pool()

    def stop(self) -> None:
        with Timer("Stop STT service pool", logger=logger):
            self.docs_bq.stop_pool()

    def _audio_array_from_bytes(self, raw_bytes: bytes) -> tuple[np.ndarray, int]:
        audio, sample_rate = sf.read(io.BytesIO(raw_bytes))
        if audio.ndim > 1:
            audio = audio[:, 0]
        audio = audio.astype(np.float32)
        audio = resample_audio(audio, sample_rate, 16_000)
        return audio, 16_000

    def _align_page_audios(
        self, raw_bytes_list: List[Optional[bytes]]
    ) -> List[Optional[str]]:
        """Align page audios in batches via sherpa decode_streams.

        Entries that are None (textless / no-audio pages) keep None and are skipped.
        """
        if not raw_bytes_list:
            return []

        align_extra = {
            "pages": len(raw_bytes_list),
            "batch_size": self.align_batch_size,
        }
        with Timer("Align page audios", logger=logger, extra=align_extra):
            aligned: List[Optional[str]] = [None] * len(raw_bytes_list)
            index_and_audio: List[tuple[int, np.ndarray]] = []
            for idx, raw_bytes in enumerate(raw_bytes_list):
                if raw_bytes is None:
                    continue
                audio, _ = self._audio_array_from_bytes(raw_bytes)
                index_and_audio.append((idx, audio))

            batch_size = self.align_batch_size
            for i in range(0, len(index_and_audio), batch_size):
                batch = index_and_audio[i : i + batch_size]
                batch_num = i // batch_size + 1
                with Timer(
                    "Align page audio batch",
                    logger=logger,
                    level=logging.DEBUG,
                    extra={"batch": batch_num, "size": len(batch)},
                ):
                    results = recognize_audios(
                        self.recognizer,
                        [audio for _, audio in batch],
                        sample_rate=16_000,
                    )
                    for (orig_idx, _), result in zip(batch, results):
                        aligned[orig_idx] = serialize_content_aligned(
                            result.merge_subwords()
                        )
            align_extra["aligned"] = sum(1 for a in aligned if a is not None)
            align_extra["skipped"] = sum(1 for a in aligned if a is None)
        return aligned

    def _heard_words_from_audio_b64(self, audio_b64: str) -> List[str]:
        with Timer("Decode and recognize audio", logger=logger, level=logging.DEBUG):
            audio, sample_rate = decode_audio_base64(audio_b64)
            audio = resample_audio(audio, sample_rate, 16_000)
            result = recognize_audio(self.recognizer, audio, 16_000)
        return [seg.word for seg in result.merge_subwords()]

    async def _ensure_page_image(
        self,
        doc_id: str,
        page_number: int,
        page_row: Dict[str, Any],
        doc_row: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        image_gcs_uri = (page_row.get("image_gcs_uri") or "").strip()
        if image_gcs_uri:
            return image_gcs_uri

        if doc_row is None:
            self.docs_bq.set_current_table("docs")
            doc_rows = await self.docs_bq.run_queries(
                DOC_SELECT_BY_ID, records=[{"id": doc_id}]
            )
            if not doc_rows or not doc_rows[0]:
                return None
            doc_row = doc_rows[0][0]

        try:
            doc_bytes = self.storage.download_bytes(doc_row["gcs_uri"])
            png_bytes = render_page_preview(
                doc_bytes, doc_row["ext"], page_number
            )
            if not png_bytes:
                return None
            image_gcs_uri = self.storage.upload_page_image(
                doc_id, page_number, png_bytes
            )
            self.pages_bq.set_current_table("pages")
            await self.pages_bq.run_queries(
                PAGE_UPDATE_IMAGE_GCS_URI,
                records=[
                    {
                        "doc_id": doc_id,
                        "page_number": page_number,
                        "image_gcs_uri": image_gcs_uri,
                    }
                ],
            )
            return image_gcs_uri
        except Exception:
            logger.exception(
                "Failed to ensure page image doc_id=%s page=%s",
                doc_id,
                page_number,
            )
            return None

    def _page_image_url(
        self,
        image_gcs_uri: str,
        include_url: bool,
    ) -> Optional[str]:
        if not include_url or not image_gcs_uri:
            return None
        return self.storage.signed_url(image_gcs_uri)

    async def insert_doc(self, req: InsertDocReq) -> StatusResponse:
        if len(req.pages) != req.pages_number:
            return StatusResponse(
                status="error",
                message=f"Expected {req.pages_number} pages, got {len(req.pages)}",
            )

        for page_number, page_req in enumerate(req.pages, start=1):
            if page_has_text(page_req.text) and not (page_req.audio and page_req.audio.strip()):
                return StatusResponse(
                    status="error",
                    message=(
                        f"Page {page_number} has text but no reference audio. "
                        "Audio is required for pages with reading text."
                    ),
                )

        doc_id = str(uuid.uuid4())
        try:
            insert_extra = {
                "doc_id": doc_id,
                "title": req.title,
                "pages": req.pages_number,
            }
            with Timer("Insert doc", logger=logger, extra=insert_extra):
                doc_bytes = base64.b64decode(req.content)
                logger.debug("Decoded doc content size_bytes=%d", len(doc_bytes))

                with Timer("Upload doc assets", logger=logger, extra={"doc_id": doc_id}):
                    gcs_uri = self.storage.upload_doc(doc_id, req.ext, doc_bytes)

                    preview_gcs_uri = None
                    preview_png = render_first_page_preview(doc_bytes, req.ext)
                    if preview_png:
                        preview_gcs_uri = self.storage.upload_preview(doc_id, preview_png)

                    page_audios: List[Optional[bytes]] = []
                    audio_gcs_uris: List[str] = []
                    total_audio_bytes = 0
                    for page_number, page_req in enumerate(req.pages, start=1):
                        has_text = page_has_text(page_req.text)
                        audio_b64 = (page_req.audio or "").strip()
                        if has_text or audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            total_audio_bytes += len(audio_bytes)
                            audio_gcs_uris.append(
                                self.storage.upload_page_audio(
                                    doc_id, page_number, audio_bytes
                                )
                            )
                            # Only align pages that have reading text.
                            page_audios.append(audio_bytes if has_text else None)
                        else:
                            audio_gcs_uris.append("")
                            page_audios.append(None)
                    logger.debug(
                        "Uploaded page audios doc_id=%s count=%d total_bytes=%d skipped=%d",
                        doc_id,
                        sum(1 for u in audio_gcs_uris if u),
                        total_audio_bytes,
                        sum(1 for a in page_audios if a is None),
                    )

                content_aligned_list = self._align_page_audios(page_audios)

                page_records: List[Dict[str, Any]] = []
                for page_number, page_req in enumerate(req.pages, start=1):
                    idx = page_number - 1
                    page_records.append(
                        Page(
                            id=str(uuid.uuid4()),
                            doc_id=doc_id,
                            page_number=page_number,
                            content=(page_req.text or "").strip(),
                            audio_gcs_uri=audio_gcs_uris[idx],
                            content_aligned=content_aligned_list[idx],
                        ).model_dump()
                    )

                doc_record = Doc(
                    id=doc_id,
                    title=req.title,
                    ext=req.ext,
                    pages_number=req.pages_number,
                    gcs_uri=gcs_uri,
                    preview_gcs_uri=preview_gcs_uri,
                ).model_dump()

                with Timer(
                    "Insert doc records",
                    logger=logger,
                    extra={"doc_id": doc_id, "pages": len(page_records)},
                ):
                    self.docs_bq.set_current_table("docs")
                    self.docs_bq.insert_records([doc_record])
                    self.pages_bq.set_current_table("pages")
                    self.pages_bq.insert_records(page_records)

            return StatusResponse(
                status="success",
                message="Document inserted successfully",
                doc_id=doc_id,
            )
        except Exception as exc:
            logger.exception("Failed to insert doc doc_id=%s", doc_id)
            try:
                self.storage.delete_doc_assets(doc_id, req.ext)
            except Exception:
                pass
            return StatusResponse(status="error", message=str(exc))

    async def list_docs(self, offset: int = 0, limit: int = 10) -> DocListResponse:
        offset = max(0, offset)
        limit = max(1, min(limit, 100))
        list_extra = {"offset": offset, "limit": limit}

        with Timer("List docs", logger=logger, extra=list_extra):
            self.docs_bq.set_current_table("docs")
            count_rows = await self.docs_bq.run_queries(DOCS_COUNT)
            total = int(count_rows[0][0]["total"]) if count_rows and count_rows[0] else 0

            page_query = DOCS_SELECT_ALL.format(
                dataset_table_id="{dataset_table_id}",
                limit=limit,
                offset=offset,
            )
            doc_rows = await self.docs_bq.run_queries(page_query)
            docs = doc_rows[0] if doc_rows and doc_rows[0] else []

            first_by_doc: Dict[str, str] = {}
            if docs:
                self.pages_bq.set_current_table("pages")
                first_page_rows = await self.pages_bq.run_queries(
                    PAGES_SELECT_FIRST,
                    records=[{"doc_id": row["id"]} for row in docs],
                )
                for result in first_page_rows:
                    if result:
                        first_by_doc[result[0]["doc_id"]] = result[0]["content"]

            items: List[DocSummary] = []
            for row in docs:
                preview_uri = row.get("preview_gcs_uri")
                image_url = self.storage.signed_url(preview_uri) if preview_uri else None
                items.append(
                    DocSummary(
                        id=row["id"],
                        title=row["title"],
                        ext=row["ext"],
                        pages_number=row["pages_number"],
                        first_page_content=first_by_doc.get(row["id"]),
                        first_page_image_url=image_url,
                    )
                )
            list_extra["total"] = total
            list_extra["returned"] = len(items)

        return DocListResponse(items=items, total=total, offset=offset, limit=limit)

    async def get_doc(self, doc_id: str, include_url: bool = True) -> Optional[DocDetailResponse]:
        extra = {"doc_id": doc_id, "include_url": include_url}
        with Timer("Get doc", logger=logger, extra=extra):
            self.docs_bq.set_current_table("docs")
            doc_rows = await self.docs_bq.run_queries(
                DOC_SELECT_BY_ID, records=[{"id": doc_id}]
            )
            if not doc_rows or not doc_rows[0]:
                extra["found"] = False
                return None

            doc = doc_rows[0][0]
            self.pages_bq.set_current_table("pages")
            page_rows = await self.pages_bq.run_queries(
                PAGES_SELECT_BY_DOC, records=[{"doc_id": doc_id}]
            )
            pages = []
            for row in page_rows[0]:
                image_gcs_uri = (row.get("image_gcs_uri") or "").strip()
                pages.append(
                    PageSummary(
                        id=row["id"],
                        page_number=row["page_number"],
                        content=row["content"] or "",
                        audio_url=(
                            self.storage.signed_url(row["audio_gcs_uri"])
                            if include_url and row.get("audio_gcs_uri")
                            else None
                        ),
                        image_url=self._page_image_url(image_gcs_uri, include_url),
                        has_text=page_has_text(row.get("content")),
                    )
                )
            content_url = self.storage.signed_url(doc["gcs_uri"]) if include_url else None
            extra["found"] = True
            extra["pages"] = len(pages)
            return DocDetailResponse(
                id=doc["id"],
                title=doc["title"],
                ext=doc["ext"],
                pages_number=doc["pages_number"],
                gcs_uri=doc["gcs_uri"],
                content_url=content_url,
                pages=pages,
            )

    async def get_page(
        self,
        doc_id: str,
        page_number: int,
        include_url: bool = True,
        ensure_image: bool | None = None,
    ) -> Optional[PageDetailResponse]:
        if ensure_image is None:
            ensure_image = include_url
        extra = {
            "doc_id": doc_id,
            "page": page_number,
            "include_url": include_url,
            "ensure_image": ensure_image,
        }
        with Timer("Get page", logger=logger, extra=extra):
            self.pages_bq.set_current_table("pages")
            rows = await self.pages_bq.run_queries(
                PAGE_SELECT, records=[{"doc_id": doc_id, "page_number": page_number}]
            )
            if not rows or not rows[0]:
                extra["found"] = False
                return None
            row = rows[0][0]
            content = row.get("content") or ""
            audio_gcs_uri = row.get("audio_gcs_uri") or ""
            image_gcs_uri = (row.get("image_gcs_uri") or "").strip()
            if ensure_image:
                image_gcs_uri = (
                    await self._ensure_page_image(doc_id, page_number, row) or image_gcs_uri
                )
            audio_url = (
                self.storage.signed_url(audio_gcs_uri)
                if include_url and audio_gcs_uri
                else None
            )
            image_url = self._page_image_url(image_gcs_uri, include_url or ensure_image)
            extra["found"] = True
            extra["has_text"] = page_has_text(content)
            return PageDetailResponse(
                id=row["id"],
                doc_id=row["doc_id"],
                page_number=row["page_number"],
                content=content,
                content_aligned=row.get("content_aligned"),
                audio_gcs_uri=audio_gcs_uri,
                audio_url=audio_url,
                image_url=image_url,
                has_text=page_has_text(content),
            )

    async def delete_doc(self, doc_id: str) -> StatusResponse:
        extra = {"doc_id": doc_id}
        with Timer("Delete doc", logger=logger, extra=extra):
            doc = await self.get_doc(doc_id, include_url=False)
            if not doc:
                extra["found"] = False
                return StatusResponse(status="error", message="Document not found")

            self.pages_bq.set_current_table("pages")
            await self.pages_bq.run_queries(PAGES_DELETE_BY_DOC, records=[{"doc_id": doc_id}])
            self.docs_bq.set_current_table("docs")
            await self.docs_bq.run_queries(DOC_DELETE_BY_ID, records=[{"id": doc_id}])
            self.storage.delete_doc_assets(doc_id, doc.ext)
            extra["found"] = True
            return StatusResponse(status="success", message="Document deleted")

    async def _update_page_content_aligned(
        self, doc_id: str, page_number: int, content_aligned: str | None
    ) -> None:
        self.pages_bq.set_current_table("pages")
        await self.pages_bq.run_queries(
            PAGE_UPDATE_CONTENT_ALIGNED,
            records=[
                {
                    "doc_id": doc_id,
                    "page_number": page_number,
                    "content_aligned": content_aligned,
                }
            ],
        )

    async def realign_page(
        self, doc_id: str, page_number: int
    ) -> PageDetailResponse:
        extra = {"doc_id": doc_id, "page": page_number}
        with Timer("Realign page", logger=logger, extra=extra):
            self.pages_bq.set_current_table("pages")
            rows = await self.pages_bq.run_queries(
                PAGE_SELECT, records=[{"doc_id": doc_id, "page_number": page_number}]
            )
            if not rows or not rows[0]:
                raise ValueError("Page not found")

            row = rows[0][0]
            content = row.get("content") or ""
            if not page_has_text(content):
                raise ValueError("Page has no reading text to align")

            audio_gcs_uri = (row.get("audio_gcs_uri") or "").strip()
            if not audio_gcs_uri:
                raise ValueError("Page has no reference audio")

            audio_bytes = self.storage.download_bytes(audio_gcs_uri)
            aligned_list = self._align_page_audios([audio_bytes])
            content_aligned = aligned_list[0]
            await self._update_page_content_aligned(
                doc_id, page_number, content_aligned
            )
            extra["aligned"] = content_aligned is not None

        page = await self.get_page(doc_id, page_number, include_url=True)
        if not page:
            raise ValueError("Page not found after realign")
        return page

    async def realign_doc(self, doc_id: str) -> RealignDocResponse:
        extra = {"doc_id": doc_id}
        with Timer("Realign document", logger=logger, extra=extra):
            self.docs_bq.set_current_table("docs")
            doc_rows = await self.docs_bq.run_queries(
                DOC_SELECT_BY_ID, records=[{"id": doc_id}]
            )
            if not doc_rows or not doc_rows[0]:
                raise ValueError("Document not found")

            self.pages_bq.set_current_table("pages")
            page_rows = await self.pages_bq.run_queries(
                PAGES_SELECT_BY_DOC, records=[{"doc_id": doc_id}]
            )
            pages = page_rows[0] if page_rows and page_rows[0] else []

            align_inputs: List[tuple[int, bytes]] = []
            skipped = 0
            for row in pages:
                content = row.get("content") or ""
                audio_gcs_uri = (row.get("audio_gcs_uri") or "").strip()
                if not page_has_text(content) or not audio_gcs_uri:
                    skipped += 1
                    continue
                align_inputs.append(
                    (row["page_number"], self.storage.download_bytes(audio_gcs_uri))
                )

            if not align_inputs:
                raise ValueError("No pages with text and audio to align")

            page_numbers = [item[0] for item in align_inputs]
            audio_bytes_list = [item[1] for item in align_inputs]
            aligned_list = self._align_page_audios(audio_bytes_list)

            for page_number, content_aligned in zip(page_numbers, aligned_list):
                await self._update_page_content_aligned(
                    doc_id, page_number, content_aligned
                )

            aligned_count = sum(1 for a in aligned_list if a is not None)
            extra["pages_aligned"] = aligned_count
            extra["pages_skipped"] = skipped
            return RealignDocResponse(
                doc_id=doc_id,
                pages_aligned=aligned_count,
                pages_skipped=skipped,
            )

    async def check_reading(
        self,
        doc_id: str,
        page_number: int,
        audio_b64: str,
        cursor: int = 0,
    ) -> CheckReadingResponse:
        check_extra = {
            "doc_id": doc_id,
            "page": page_number,
            "cursor": cursor,
        }
        with Timer("Check reading", logger=logger, extra=check_extra):
            page = await self.get_page(doc_id, page_number, include_url=False)
            if not page:
                raise ValueError("Page not found")

            expected_words = tokenize_text(page.content)
            # Picture-only / empty pages are already complete — no STT needed.
            if not expected_words:
                check_extra["new_cursor"] = 0
                check_extra["mismatches"] = 0
                check_extra["page_complete"] = True
                check_extra["empty_page"] = True
                return CheckReadingResponse(
                    ok=True,
                    cursor=0,
                    mismatches=[],
                    page_complete=True,
                )

            heard_words = self._heard_words_from_audio_b64(audio_b64)
            logger.debug(
                "Check reading heard_words=%d expected_words=%d",
                len(heard_words),
                len(expected_words),
            )
            new_cursor, raw_mismatches = compare_utterance(
                expected_words, heard_words, cursor
            )

            mismatches: List[WordMismatch] = []
            if raw_mismatches:
                segments = parse_content_aligned(page.content_aligned)

                for index, expected, heard in raw_mismatches:
                    seg_idx = fuzzy_match_segment_index(expected, segments, index)
                    start = segments[seg_idx].start if seg_idx >= 0 else None
                    end = segments[seg_idx].end if seg_idx >= 0 else None
                    mismatches.append(
                        WordMismatch(
                            index=index,
                            expected=expected,
                            heard=heard,
                            start=start,
                            end=end,
                        )
                    )

            page_complete = new_cursor >= len(expected_words)
            check_extra["new_cursor"] = new_cursor
            check_extra["mismatches"] = len(mismatches)
            check_extra["page_complete"] = page_complete
            return CheckReadingResponse(
                ok=len(mismatches) == 0,
                cursor=new_cursor,
                mismatches=mismatches,
                page_complete=page_complete,
            )

    def build_final_score(
        self,
        doc_id: str,
        words_total: int,
        words_correct: int,
        pages_completed: int,
        pages_total: int,
    ) -> FinalScoreResponse:
        accuracy = (words_correct / words_total) if words_total else 0.0
        return FinalScoreResponse(
            doc_id=doc_id,
            words_total=words_total,
            words_correct=words_correct,
            pages_completed=pages_completed,
            pages_total=pages_total,
            accuracy=round(accuracy, 4),
        )
