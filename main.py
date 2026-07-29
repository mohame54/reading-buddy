import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import admin, docs, reading
from src.services.bootstrap import bootstrap_tables
from src.services.storage_service import StorageService
from src.services.stt_service import STTService


@asynccontextmanager
async def lifespan(app: FastAPI):
    model_dir = os.getenv("MODEL_DIR", "models")
    num_threads = int(os.getenv("STT_NUM_THREADS", "2"))
    align_batch_size = int(os.getenv("STT_ALIGN_BATCH_SIZE", "4"))
    bucket_name = os.environ["GCS_BUCKET"]

    storage = StorageService(bucket_name=bucket_name)
    stt_service = STTService(
        model_dir=model_dir,
        storage=storage,
        num_threads=num_threads,
        align_batch_size=align_batch_size,
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

app.include_router(admin.router)
app.include_router(docs.router)
app.include_router(reading.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
