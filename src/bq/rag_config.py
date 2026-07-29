import os
import logging
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from google.cloud import bigquery
    from .text_indices import BQTextEmbeddingIndex

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BQRagConfig:
    table_name: str
    schema_key: str
    txt_model_name: str
    embedding_column: str


def load_bq_rag_config() -> BQRagConfig:
    table_name = os.getenv("BQ_TABLE_NAME", "schema_chunks")
    txt_model_name = os.getenv("BQ_TEXT_MODEL_NAME")
    if not txt_model_name:
        raise ValueError("BQ_TEXT_MODEL_NAME is not set")
    schema_key = os.getenv("BQ_SCHEMA_KEY") or table_name
    embedding_column = os.getenv("BQ_EMBEDDING_COLUMN", "embedding")
    return BQRagConfig(
        table_name=table_name,
        schema_key=schema_key,
        txt_model_name=txt_model_name,
        embedding_column=embedding_column,
    )


def default_embedding_dim_for_model(model_name: str) -> Optional[int]:
    normalized = model_name.strip().lower()
    if normalized.startswith("gemini-embedding"):
        return 3072
    if normalized.startswith("text-embedding") or "multilingual" in normalized:
        return 768
    return None


def probe_stored_embedding_dim(
    client: "bigquery.Client",
    table_query_path: str,
    embedding_column: str,
) -> Optional[int]:
    query = f"""
    SELECT ARRAY_LENGTH({embedding_column}) AS dim
    FROM {table_query_path}
    WHERE {embedding_column} IS NOT NULL
      AND ARRAY_LENGTH({embedding_column}) > 0
    LIMIT 1
    """
    try:
        result = client.query(query).result()
        row = next(iter(result), None)
        if row and row.dim:
            return int(row.dim)
    except Exception as exc:
        logger.warning(
            "Could not probe embedding dimension from %s: %s",
            table_query_path,
            exc,
        )
    return None


def resolve_embedding_dim(
    client: "bigquery.Client",
    table_query_path: str,
    embedding_column: str,
    model_name: str,
    explicit_dim: Optional[int] = None,
) -> Optional[int]:
    if explicit_dim is not None:
        return explicit_dim

    probed = probe_stored_embedding_dim(client, table_query_path, embedding_column)
    if probed is not None:
        logger.info(
            "Using embedding dimension %s from stored vectors in %s",
            probed,
            table_query_path,
        )
        return probed

    model_default = default_embedding_dim_for_model(model_name)
    if model_default is not None:
        logger.info(
            "Using default embedding dimension %s for model %s",
            model_default,
            model_name,
        )
    return model_default


def create_text_embedding_index(
    *,
    proj_dataset_id: str,
    schema_path: Optional[str] = None,
    table_name: Optional[str] = None,
    schema_key: Optional[str] = None,
    txt_model_name: Optional[str] = None,
    embedding_column: Optional[str] = None,
    pool_num_workers: Optional[int] = 1,
    pool_query_timeout_secs: Optional[int] = 60,
    use_shared_pool: Optional[bool] = True,
) -> "BQTextEmbeddingIndex":
    from .text_indices import BQTextEmbeddingIndex

    config = load_bq_rag_config()
    resolved_table = table_name or config.table_name
    index = BQTextEmbeddingIndex(
        proj_dataset_id=proj_dataset_id,
        txt_model_name=txt_model_name or config.txt_model_name,
        schema_path=schema_path,
        schema_key=schema_key or config.schema_key,
        embedding_column=embedding_column or config.embedding_column,
        pool_num_workers=pool_num_workers,
        pool_query_timeout_secs=pool_query_timeout_secs,
        use_shared_pool=use_shared_pool,
    )
    index.set_current_table(resolved_table)
    return index
