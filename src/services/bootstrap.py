import logging

from src.bq.base import BigQueryIndexBase

logger = logging.getLogger(__name__)


def ensure_table(bq: BigQueryIndexBase, table_name: str, schema_key: str) -> None:
    bq.set_schema_key(schema_key)
    tables = bq.get_tables()
    if table_name not in tables:
        logger.info("Creating BigQuery table '%s'", table_name)
        bq.create_table(table_name)
    else:
        bq.set_current_table(table_name)
        logger.info("BigQuery table '%s' already exists", table_name)
        _ensure_schema_columns(bq, table_name)


def _ensure_schema_columns(bq: BigQueryIndexBase, table_name: str) -> None:
    """Add any schema.json columns missing from an existing table."""
    table = bq.client.get_table(bq.table_info.table_id)
    existing = {field.name for field in table.schema}
    missing = [field for field in bq.schema_fields if field.name not in existing]
    if not missing:
        return
    logger.info(
        "Adding columns %s to BigQuery table '%s'",
        [f.name for f in missing],
        table_name,
    )
    table.schema = list(table.schema) + missing
    bq.client.update_table(table, ["schema"])


def bootstrap_tables(docs_bq: BigQueryIndexBase, pages_bq: BigQueryIndexBase) -> None:
    ensure_table(docs_bq, "docs", "docs")
    ensure_table(pages_bq, "pages", "pages")
