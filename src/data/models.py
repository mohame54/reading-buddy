from pydantic import BaseModel


class Page(BaseModel):
    id: str
    doc_id: str
    page_number: int
    content: str
    audio_gcs_uri: str
    content_aligned: str | None = None


class Doc(BaseModel):
    id: str
    title: str
    ext: str
    pages_number: int
    gcs_uri: str
    preview_gcs_uri: str | None = None
