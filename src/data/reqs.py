from pydantic import BaseModel, Field
from typing import List, Optional


class InsertPageReq(BaseModel):
    text: str = Field(
        default="",
        description="The text content of the page (empty for picture-only / non-reading pages)",
    )
    audio: str | None = Field(
        default=None,
        description="Base64 reference audio; required when text is non-empty, optional otherwise",
    )


class InsertDocReq(BaseModel):
    title: str
    ext: str
    pages_number: int
    pages: List[InsertPageReq]
    content: str = Field(..., description="The base64 encoded content of the document")


class StatusResponse(BaseModel):
    status: str = Field(..., description="The status of the request")
    message: str | None = Field(None, description="The message of the request")
    doc_id: str | None = Field(None, description="Created document id")


class RealignDocResponse(BaseModel):
    doc_id: str
    pages_aligned: int
    pages_skipped: int


class DocSummary(BaseModel):
    id: str
    title: str
    ext: str
    pages_number: int
    first_page_content: str | None = None
    first_page_image_url: str | None = None


class DocListResponse(BaseModel):
    items: List[DocSummary] = Field(default_factory=list)
    total: int
    offset: int
    limit: int


class PageSummary(BaseModel):
    id: str
    page_number: int
    content: str
    audio_url: str | None = None
    image_url: str | None = None
    has_text: bool = True


class DocDetailResponse(BaseModel):
    id: str
    title: str
    ext: str
    pages_number: int
    gcs_uri: str
    content_url: str | None = None
    pages: List[PageSummary] = Field(default_factory=list)


class PageDetailResponse(BaseModel):
    id: str
    doc_id: str
    page_number: int
    content: str
    content_aligned: str | None = None
    audio_gcs_uri: str = ""
    audio_url: str | None = None
    image_url: str | None = None
    has_text: bool = True


class WordMismatch(BaseModel):
    index: int
    expected: str
    heard: str | None = None
    start: float | None = None
    end: float | None = None


class CheckReadingReq(BaseModel):
    doc_id: str
    page_number: int
    audio: str = Field(
        default="",
        description="Base64 child utterance; ignored for textless pages",
    )
    cursor: int = 0


class CheckReadingResponse(BaseModel):
    ok: bool
    cursor: int
    mismatches: List[WordMismatch] = Field(default_factory=list)
    page_complete: bool = False


class FinishReadingReq(BaseModel):
    doc_id: str
    words_total: int
    words_correct: int
    pages_completed: int


class FinalScoreResponse(BaseModel):
    doc_id: str
    words_total: int
    words_correct: int
    pages_completed: int
    pages_total: int
    accuracy: float
