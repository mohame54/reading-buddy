import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    return int(raw) if raw is not None else default


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    return float(raw) if raw is not None else default


@dataclass(frozen=True)
class Settings:
    # Logging
    log_level: str

    # STT / alignment
    stt_num_threads: int
    stt_align_batch_size: int
    stt_frame_duration: float
    stt_fuzzy_match_threshold: float

    # BigQuery process pool
    bq_pool_num_workers: int
    bq_pool_query_timeout: int
    bq_pool_ready_timeout: float
    bq_pool_max_queue_size: Optional[int]
    bq_pool_queue_put_timeout: float

    # BigQuery load-job retry
    bq_load_job_max_attempts: int
    bq_load_job_retry_initial_delay: float
    bq_load_job_retry_max_delay: float


@lru_cache
def get_settings() -> Settings:
    align_batch_raw = os.getenv("STT_ALIGN_BATCH_SIZE") or os.getenv("ALIGN_BATCH_SIZE") or "4"
    max_queue_raw = _env_int("BQ_POOL_MAX_QUEUE_SIZE", 50)

    return Settings(
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        stt_num_threads=_env_int("STT_NUM_THREADS", 2),
        stt_align_batch_size=int(align_batch_raw),
        stt_frame_duration=_env_float("STT_FRAME_DURATION", 0.08),
        stt_fuzzy_match_threshold=_env_float("STT_FUZZY_MATCH_THRESHOLD", 0.6),
        bq_pool_num_workers=_env_int("BQ_POOL_NUM_WORKERS", 1),
        bq_pool_query_timeout=_env_int("BQ_POOL_QUERY_TIMEOUT", 30),
        bq_pool_ready_timeout=_env_float("BQ_POOL_READY_TIMEOUT", 5.0),
        bq_pool_max_queue_size=None if max_queue_raw == 0 else max_queue_raw,
        bq_pool_queue_put_timeout=_env_float("BQ_POOL_QUEUE_PUT_TIMEOUT_SECS", 10.0),
        bq_load_job_max_attempts=_env_int("BQ_LOAD_JOB_MAX_ATTEMPTS", 5),
        bq_load_job_retry_initial_delay=_env_float(
            "BQ_LOAD_JOB_RETRY_INITIAL_DELAY_SECS", 1.0
        ),
        bq_load_job_retry_max_delay=_env_float("BQ_LOAD_JOB_RETRY_MAX_DELAY_SECS", 16.0),
    )
