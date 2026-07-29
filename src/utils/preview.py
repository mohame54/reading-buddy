import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "gif"}


def render_first_page_preview(doc_bytes: bytes, ext: str, scale: float = 2.0) -> Optional[bytes]:
    """
    Build a PNG preview of the document's first page for library cards.
    PDFs are rasterized; image uploads are re-encoded as PNG.
    """
    ext = ext.lstrip(".").lower()
    try:
        if ext == "pdf":
            return _preview_from_pdf(doc_bytes, scale=scale)
        if ext in IMAGE_EXTS:
            return _preview_from_image(doc_bytes)
    except Exception:
        logger.exception("Failed to render first-page preview (ext=%s)", ext)
    return None


def _preview_from_pdf(doc_bytes: bytes, scale: float) -> bytes:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(doc_bytes)
    if len(pdf) < 1:
        raise ValueError("PDF has no pages")
    page = pdf[0]
    bitmap = page.render(scale=scale)
    image = bitmap.to_pil()
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _preview_from_image(doc_bytes: bytes) -> bytes:
    from PIL import Image

    image = Image.open(io.BytesIO(doc_bytes))
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
