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
    return render_page_preview(doc_bytes, ext, page_number=1, scale=scale)


def render_page_preview(
    doc_bytes: bytes,
    ext: str,
    page_number: int,
    scale: float = 2.0,
) -> Optional[bytes]:
    """
    Build a PNG for a single document page (1-based page index).
    PDFs are rasterized; image uploads only support page 1.
    """
    ext = ext.lstrip(".").lower()
    if page_number < 1:
        return None
    try:
        if ext == "pdf":
            return _preview_from_pdf(doc_bytes, page_number=page_number, scale=scale)
        if ext in IMAGE_EXTS:
            if page_number != 1:
                return None
            return _preview_from_image(doc_bytes)
    except Exception:
        logger.exception(
            "Failed to render page preview (ext=%s, page=%s)",
            ext,
            page_number,
        )
    return None


def _preview_from_pdf(doc_bytes: bytes, page_number: int, scale: float) -> bytes:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(doc_bytes)
    if page_number > len(pdf):
        raise ValueError(f"PDF has only {len(pdf)} page(s), requested page {page_number}")
    page = pdf[page_number - 1]
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
