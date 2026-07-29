from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_stt_service
from src.data.reqs import DocListResponse
from src.services.stt_service import STTService

router = APIRouter(prefix="/docs", tags=["docs"])


@router.get("/{offset}/{limit}", response_model=DocListResponse)
async def list_docs(
    offset: int,
    limit: int,
    stt: STTService = Depends(get_stt_service),
):
    """Paginated library list. `GET /docs/10/10` → items 11–20."""
    return await stt.list_docs(offset=offset, limit=limit)


@router.get("/{doc_id}")
async def get_doc(doc_id: str, stt: STTService = Depends(get_stt_service)):
    doc = await stt.get_doc(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{doc_id}/pages/{page_number}")
async def get_page(
    doc_id: str, page_number: int, stt: STTService = Depends(get_stt_service)
):
    page = await stt.get_page(doc_id, page_number)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page
