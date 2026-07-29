from .indices import BQEmbeddingIndex
from .rag_config import load_bq_rag_config, create_text_embedding_index, BQRagConfig
from .base import BigQueryIndexBase
from .pool import BigQueryProcessPool
from .pool_manager import (
    get_shared_pool,
    stop_all_shared_pools,
    get_pool_manager_status,
    BigQueryPoolManager,
)

__all__ = [
    "BQEmbeddingIndex",
    "BQTextEmbeddingIndex",
    "BigQueryIndexBase",
    "BQRagConfig",
    "load_bq_rag_config",
    "create_text_embedding_index",
    "BigQueryProcessPool",
    "get_shared_pool",
    "stop_all_shared_pools",
    "get_pool_manager_status",
    "BigQueryPoolManager",
]


def __getattr__(name: str):
    if name == "BQTextEmbeddingIndex":
        from .text_indices import BQTextEmbeddingIndex

        return BQTextEmbeddingIndex
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
