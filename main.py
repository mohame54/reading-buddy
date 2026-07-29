import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import get_settings
from src.api import admin, docs, reading
from src.services.bootstrap import bootstrap_tables
from src.services.storage_service import StorageService
from src.services.stt_service import STTService
from src.utils.decorators import Timer

logger = logging.getLogger(__name__)

_settings = get_settings()
_log_level = _settings.log_level
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        extra = {"method": request.method, "path": request.url.path}
        path = request.url.path
        level = logging.DEBUG if path == "/health" else logging.INFO
        with Timer(
            "HTTP request",
            logger=logger,
            extra=extra,
            level=level,
            duration_unit="ms",
        ):
            response = await call_next(request)
            extra["status"] = response.status_code
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    model_dir = os.getenv("MODEL_DIR", "models")
    bucket_name = os.environ["GCS_BUCKET"]

    storage = StorageService(bucket_name=bucket_name)
    stt_service = STTService(
        model_dir=model_dir,
        storage=storage,
        num_threads=settings.stt_num_threads,
        align_batch_size=settings.stt_align_batch_size,
    )
    bootstrap_tables(stt_service.docs_bq, stt_service.pages_bq)
    stt_service.start()
    app.state.stt_service = stt_service
    yield
    stt_service.stop()


app = FastAPI(title="Reading Buddy API", lifespan=lifespan)

cors_origins = os.getenv("CORS_ORIGINS", "*")
origins = ["*"] if cors_origins == "*" else [o.strip() for o in cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestTimingMiddleware)

app.include_router(admin.router)
app.include_router(docs.router)
app.include_router(reading.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
