import os
import json
import time
import uuid
import logging
import threading
from datetime import date, datetime
from typing import List, Optional, Dict, Any, Set
from dataclasses import dataclass
from google.api_core.exceptions import TooManyRequests
from google.cloud import bigquery
from .pool import BigQueryProcessPool
from .pool_manager import get_shared_pool
from .utils import load_bq_client, setup_vertex_ai
from .queries import VEC_SEARCH_CREATE_QUERY

logger = logging.getLogger(__name__)


@dataclass
class TableInfo:
    """Data class to hold table information."""
    table_id: str = ""
    table_name: str = ""
    query_path: str = ""


class BigQueryIndexBase:
    """
    Base class for BigQuery operations with vector search capabilities.
    
    Provides common functionality for table management, schema handling,
    and CRUD operations on BigQuery datasets.
    """
    
    # Constants
    MIN_RECORDS_FOR_INDEX = 5000
    DEFAULT_NUM_LISTS = 5
    _load_job_locks: Dict[str, threading.Lock] = {}
    _load_job_locks_guard = threading.Lock()
    
    def __init__(
        self,
        proj_dataset_id: str,
        schema_path: Optional[str] = None,
        schema_key: Optional[str]="Hotels",
        pool_num_workers: Optional[int] = None,
        pool_query_timeout_secs: Optional[int] = None,
        use_shared_pool: Optional[bool] = True,
        skip_vertex_init: bool = False,
    ):
        """
        Initialize BigQuery client and setup project configuration.
        
        Args:
            proj_dataset_id: Project and dataset ID in format 'project.dataset'
            schema_path: Path to JSON schema file
            schema_key: Key for schema in JSON file
            pool_num_workers: Number of workers for pool (only used if not using shared pool)
            pool_query_timeout_secs: Query timeout in seconds
            use_shared_pool: If True, uses a shared pool across all indices (recommended)
        """
        if pool_num_workers is None:
            pool_num_workers = int(os.getenv("BQ_POOL_NUM_WORKERS", "1"))
        if pool_query_timeout_secs is None and not use_shared_pool:
            pool_query_timeout_secs = int(os.getenv("BQ_POOL_QUERY_TIMEOUT", "30"))
        self.pool_num_workers = pool_num_workers
        self.pool_timeout = pool_query_timeout_secs
        self.use_shared_pool = use_shared_pool
        self.skip_vertex_init = skip_vertex_init
        self.tables_names = None
        self.schema_path = schema_path
        self.schema_key = schema_key
        self._validate_credentials()
        self._setup_project_info(proj_dataset_id)
        self._initialize_client()
        self._load_schema(schema_path, schema_key)
        self._reset_table_info()
    
    def set_schema_key(self, schema_key: str) -> None:
        self.schema_key = schema_key
        self._load_schema(self.schema_path, schema_key)
    
    def _validate_credentials(self) -> None:
        """Validate Google credentials are available."""
        if not os.environ.get("GOOGLE_CREDENTIALS"):
            raise ValueError("GOOGLE_CREDENTIALS environment variable not set")
    
    def _setup_project_info(self, proj_dataset_id: str) -> None:
        """Setup project and dataset information."""
        try:
            self.proj_id, self.dataset_id = proj_dataset_id.split(".", 1)
        except ValueError:
            raise ValueError(
                f"Invalid proj_dataset_id format: '{proj_dataset_id}'. "
                "Expected format: 'project_id.dataset_id'"
            )
        
        self.proj_dataset_id = proj_dataset_id
        
        # Handle project IDs with hyphens
        self._quoted_proj_id = f"`{self.proj_id}`" if "-" in self.proj_id else self.proj_id
        self._quoted_dataset_id = f"`{self.dataset_id}`" if "-" in self.dataset_id else self.dataset_id
    
    def _initialize_client(self) -> None:
        start_time = time.time()
        logger.info(f"🔧 Initializing BigQuery client for project={self.proj_id}, dataset={self.dataset_id}")
        
        creds_info = os.environ["GOOGLE_CREDENTIALS"]
        if not creds_info:
           raise ValueError("`GOOGLE_CREDENTIALS` Env var wasn't found!") 
        self.client = load_bq_client(creds_info, self.proj_id, from_b64=True, force_new=False)
        
        # Use shared pool or create dedicated pool
        if self.use_shared_pool:
            logger.info(f"♻️  Using shared pool for project '{self.proj_id}'")
            self.client_pool = get_shared_pool(
                proj_id=self.proj_id,
                num_workers=self.pool_num_workers,
                query_timeout=self.pool_timeout,
                auto_start=False  # We'll start it manually
            )
            self._owns_pool = False
        else:
            logger.info(f"🔨 Creating dedicated pool with {self.pool_num_workers} workers")
            self.client_pool = BigQueryProcessPool(
                proj_id=self.proj_id, 
                num_workers=self.pool_num_workers, 
                query_timeout=self.pool_timeout
            )
            self._owns_pool = True
        
        if not self.skip_vertex_init:
            setup_vertex_ai(creds_info, proj_id=self.proj_id, from_b64=True)
        
        self.dataset_ref = self.client.dataset(self.dataset_id)
        
        elapsed = time.time() - start_time
        pool_type = "shared" if self.use_shared_pool else "dedicated"
        logger.info(f"✅ BigQuery client initialized in {elapsed:.3f}s with {pool_type} pool")
    
    def _load_schema(self, schema_path, schema_key) -> None:
        """Load and process schema from JSON file or use default."""
        if schema_path:
            try:
                with open(schema_path, 'r') as f:
                    schema_data = json.load(f)
                    if schema_key:
                        if schema_key not in schema_data:
                            raise ValueError(f"Error couldn't find {schema_key} in schema data: {schema_data}")
                        schema_data = schema_data[schema_key]
                self._process_schema(schema_data)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                raise ValueError(f"Error loading schema from {schema_path}: {e}")
        else:
            self._set_default_schema()
    
    def _process_schema(self, schema_data: List[Dict[str, Any]]) -> None:
        """Process schema data into BigQuery schema fields."""
        self.schema_json = {field['name']: field for field in schema_data}
        self.schema_fields = [
            bigquery.SchemaField(field['name'], field['type'], field['mode'])
            for field in schema_data
        ]
        self.column_names = {field['name'] for field in schema_data}
    
    def _set_default_schema(self) -> None:
        """Set default empty schema."""
        self.schema_json = {}
        self.schema_fields = []
        self.column_names = set()
    
    def _reset_table_info(self) -> None:
        """Reset current table information."""
        self.table_info = TableInfo()
    
    def _format_table_name(self, table_name: str) -> str:
        """Format table name with backticks if contains special characters."""
        special_chars = ".- "
        if any(char in table_name for char in special_chars):
            return f"`{table_name}`"
        return table_name
    
    def _validate_table_set(self) -> None:
        """Validate that a table is currently set."""
        if not self.table_info.query_path:
            available_tables = self.get_tables()
            raise ValueError(
                f"No table set. Available tables: {available_tables}. "
                "Use set_current_table() first."
            )
    
    def _validate_table(self, table_name: str, exists: Optional[bool] = True) -> None:
        """Validate that a table exists in the dataset."""
        available_tables = self.get_tables()
        if exists and table_name not in available_tables:
            raise ValueError(
                f"Table '{table_name}' not found. Available tables: {available_tables}"
            )
        elif exists and table_name in available_tables:
            raise ValueError(
                f"Table '{table_name}' already exists. Available tables: {available_tables}"
            )

    @property
    def current_table_name(self) -> str:
        """Get the current table name."""
        return self.table_info.table_name
    
    @property
    def record_count(self) -> int:
        """Get the number of records in the current table."""
        self._validate_table_set()
        
        start_time = time.time()
        logger.debug(f"🔢 Counting records in {self.table_info.table_name}...")
        
        query = f"SELECT COUNT(*) as num_records FROM {self.table_info.query_path}"
        job = self.client.query(query)
        result = job.result()
        count = next(iter(result)).num_records
        
        elapsed = time.time() - start_time
        logger.debug(f"✅ Record count: {count} (took {elapsed:.3f}s)")
        
        return count
    
    def set_current_table(self, table_name: str, prefix: Optional[str] = None) -> None:
        """
        Set the current table for operations.
        
        Args:
            table_name: Base table name
            prefix: Optional prefix to append to table name
        """
        full_table_name = f"{table_name}_{prefix}" if prefix else table_name
        formatted_table_name = self._format_table_name(full_table_name)
        
        self.table_info = TableInfo(
            table_id=f"{self.proj_dataset_id}.{full_table_name}",
            table_name=full_table_name,
            query_path=f"{self._quoted_proj_id}.{self._quoted_dataset_id}.{formatted_table_name}"
        )
    
    def get_tables(self) -> Set[str]:
        """Get all table names in the dataset."""
        try:
            if self.tables_names is None:
                start_time = time.time()
                logger.debug(f"📋 Listing tables in dataset {self.dataset_id}...")
                self.tables_names = {table.table_id for table in self.client.list_tables(self.proj_dataset_id)}
                elapsed = time.time() - start_time
                logger.debug(f"✅ Found {len(self.tables_names)} table(s) in {elapsed:.3f}s")
            return self.tables_names
        except Exception as e:
            logger.error(f"❌ Failed to list tables: {e}")
            raise RuntimeError(f"Failed to list tables: {e}")
    
    
    def create_table(self, table_name: str, prefix: Optional[str] = None) -> None:
        """
        Create a new table with the loaded schema.
        
        Args:
            table_name: Base table name
            prefix: Optional prefix for table name
        """
        full_name = f"{table_name}_{prefix}" if prefix else table_name
        self._validate_table(full_name, False)
        
        self.set_current_table(table_name, prefix)
        
        start_time = time.time()
        logger.info(f"🏗️  Creating table '{full_name}' with {len(self.schema_fields)} field(s)...")
        
        try:
            table = bigquery.Table(self.table_info.table_id, schema=self.schema_fields)
            table.expires = None
            self.client.create_table(table)
            
            elapsed = time.time() - start_time
            logger.info(f"✅ Table '{full_name}' created successfully in {elapsed:.3f}s")
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ Failed to create table '{full_name}' after {elapsed:.3f}s: {e}")
            raise RuntimeError(f"Failed to create table '{full_name}': {e}")
    
    def delete_table(self, table_name: str) -> None:
        """
        Delete a table from the dataset.
        
        Args:
            table_name: Name of the table to delete
        """
        self._validate_table(table_name)
        self.set_current_table(table_name)
        
        start_time = time.time()
        logger.info(f"🗑️  Deleting table '{table_name}'...")
        
        try:
            self.client.delete_table(self.table_info.table_id)
            self._reset_table_info()
            
            elapsed = time.time() - start_time
            logger.info(f"✅ Table '{table_name}' deleted successfully in {elapsed:.3f}s")
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ Failed to delete table '{table_name}' after {elapsed:.3f}s: {e}")
            raise RuntimeError(f"Failed to delete table '{table_name}': {e}")
    
    def setup_vector_search(
        self,
        table_name: str,
        index_name: str = "index",
        embedding_column: str = "text_embd",
        num_lists: int = None
    ) -> bigquery.QueryJob:
        """
        Setup vector search index on the specified table.
        
        Args:
            table_name: Name of the table to index
            index_name: Name for the vector index
            embedding_column: Name of the embedding column
            num_lists: Number of lists for the index
            
        Returns:
            BigQuery job result
        """
        self._validate_table(table_name)
        self.set_current_table(table_name)
        
        num_lists = num_lists or self.DEFAULT_NUM_LISTS
        
        record_count = self.record_count
        if record_count < self.MIN_RECORDS_FOR_INDEX:
            raise ValueError(
                f"Table must have at least {self.MIN_RECORDS_FOR_INDEX} records "
                f"to create an index. Current count: {record_count}"
            )
        
        start_time = time.time()
        logger.info(f"🔍 Creating vector search index '{index_name}' on {table_name}.{embedding_column} with {num_lists} lists...")
        
        query = (VEC_SEARCH_CREATE_QUERY
                .replace("{num_lists}", str(num_lists))
                .replace("{index_name}", index_name)
                .replace("{dataset_table_id}", self.table_info.query_path)
                .replace("{embd_name}", embedding_column))
        
        try:
            job = self.client.query(query)
            result = job.result()
            
            elapsed = time.time() - start_time
            logger.info(f"✅ Vector search index created successfully in {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ Failed to create vector search index after {elapsed:.3f}s: {e}")
            raise RuntimeError(f"Failed to create vector search index: {e}")
    
    def insert_records(self, records: List[Dict[str, Any]]) -> None:
        """
        Insert records into the current table using BigQuery load jobs.
        
        Args:
            records: List of record dictionaries to insert
        """
        self._insert_records(records, self._insert_records_load_job)

    def insert_records_streaming(self, records: List[Dict[str, Any]]) -> None:
        """
        Insert records into the current table using BigQuery streaming inserts.

        This avoids BigQuery table update quotas for bursty small inserts, but callers
        should only use it for append-only rows that do not need immediate DML updates.
        """
        self._insert_records(records, self._insert_records_streaming)

    def _insert_records(self, records: List[Dict[str, Any]], insert_func) -> None:
        self._validate_table_set()
        
        if not records:
            raise ValueError("No records provided for insertion")
        
        start_time = time.time()
        num_records = len(records)
        logger.info(f"💾 Inserting {num_records} record(s) into {self.table_info.table_name}...")
        
        try:
            insert_func(records)
            
            elapsed = time.time() - start_time
            logger.info(f"✅ Inserted {num_records} record(s) successfully in {elapsed:.3f}s (avg: {elapsed/num_records:.3f}s per record)")
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ Failed to insert {num_records} record(s) after {elapsed:.3f}s: {e}")
            raise RuntimeError(f"Failed to insert records: {e}")

    def _insert_records_streaming(self, records: List[Dict[str, Any]]) -> None:
        table_ref = self.client.dataset(self.dataset_id).table(self.table_info.table_name)
        json_records = [self._json_safe_record(record) for record in records]
        row_ids = [str(record.get("id") or uuid.uuid4()) for record in records]

        errors = self.client.insert_rows_json(
            table_ref,
            json_records,
            row_ids=row_ids,
        )
        if errors:
            raise RuntimeError(f"Streaming insert failed: {errors}")

    def _insert_records_load_job(self, records: List[Dict[str, Any]]) -> None:
        with self._get_load_job_lock():
            self._insert_records_load_job_with_retry(records)

    def _insert_records_load_job_with_retry(self, records: List[Dict[str, Any]]) -> None:
        max_attempts = int(os.getenv("BQ_LOAD_JOB_MAX_ATTEMPTS", "5"))
        retry_delay = float(os.getenv("BQ_LOAD_JOB_RETRY_INITIAL_DELAY_SECS", "1.0"))
        max_delay = float(os.getenv("BQ_LOAD_JOB_RETRY_MAX_DELAY_SECS", "16.0"))

        for attempt in range(1, max_attempts + 1):
            try:
                self._run_insert_records_load_job(records)
                return
            except TooManyRequests:
                if attempt == max_attempts:
                    raise
                logger.warning(
                    "BigQuery load-job insert for %s hit rate limit; retrying in %.1fs "
                    "(attempt %d/%d)",
                    self.table_info.table_name,
                    retry_delay,
                    attempt + 1,
                    max_attempts,
                )
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_delay)

    def _run_insert_records_load_job(self, records: List[Dict[str, Any]]) -> None:
        table_ref = self.client.dataset(self.dataset_id).table(self.table_info.table_name)
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            schema=self.schema_fields,
        )

        job = self.client.load_table_from_json(
            [self._json_safe_record(record) for record in records],
            table_ref,
            job_config=job_config,
        )
        job.result()

    def _get_load_job_lock(self) -> threading.Lock:
        with self._load_job_locks_guard:
            return self._load_job_locks.setdefault(
                self.table_info.table_id,
                threading.Lock(),
            )

    @staticmethod
    def _json_safe_record(record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: value.isoformat() if isinstance(value, (date, datetime)) else value
            for key, value in record.items()
        }

    @staticmethod
    def _query_parameter_type(schema_type: str) -> str:
        """Convert BigQuery schema types to query parameter type names."""
        return {
            "BOOLEAN": "BOOL",
            "INTEGER": "INT64",
            "FLOAT": "FLOAT64",
        }.get(schema_type, schema_type)
    
    
    def _build_query_parameters(self, metadata: Dict[str, Any]):
        """Build query parameters from metadata dictionary."""
        parameters = []
        
        for key, value in metadata.items():
            if key not in self.schema_json:
                allowed_keys = list(self.schema_json.keys())
                raise ValueError(f"key {key} doesn't exist into the db allowed keys are: {allowed_keys}")
                
            field_info = self.schema_json[key]
            parameter_type = self._query_parameter_type(field_info['type'])
            
            if field_info['mode'] == "REPEATED":
                parameters.append(
                    bigquery.ArrayQueryParameter(key, parameter_type, value)
                )
            else:
                parameters.append(
                    bigquery.ScalarQueryParameter(key, parameter_type, value)
                )
        return bigquery.QueryJobConfig(query_parameters=parameters)
    
    def update_records(self, base_query: str, records: List[Dict[str, Any]]) -> None:
        """
        Update records using a base query template.
        
        Args:
            base_query: Query template with {dataset_table_id} placeholder
            records: List of record dictionaries with update data
        """
        self._validate_table_set()
        
        start_time = time.time()
        num_records = len(records)
        logger.info(f"🔄 Updating {num_records} record(s) in {self.table_info.table_name}...")
        
        query_template = base_query.format(dataset_table_id=self.table_info.query_path)
        
        for idx, record in enumerate(records, 1):
            try:
                job_config = self._build_query_parameters(record)
                query_job = self.client.query(query_template, job_config=job_config)
                query_job.result()
                
                if idx % 10 == 0 or idx == num_records:
                    logger.debug(f"   Progress: {idx}/{num_records} records updated")
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"❌ Failed to update record {idx}/{num_records} after {elapsed:.3f}s: {e}")
                raise RuntimeError(f"Failed to update record {record}: {e}")
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Updated {num_records} record(s) in {elapsed:.3f}s (avg: {elapsed/num_records:.3f}s per record)")
            
    async def run_queries(self, base_query, records=[]):
        """
        Execute parameterized BigQuery queries asynchronously.
        
        This method provides a high-level interface for running queries with parameters
        against the current table. It automatically handles query templating, parameter
        binding, and pool execution.
        
        Args:
            base_query: SQL query template with {dataset_table_id} placeholder and 
                       optional @parameter placeholders for query parameters.
                       Example: "SELECT * FROM {dataset_table_id} WHERE id = @id"
            
            records: List of dictionaries containing parameter values. Each dictionary
                    represents parameters for one query execution. Parameter keys must
                    match both the schema and the @parameter names in the query.
                    If empty, executes query once without parameters.
        
        Returns:
            List of query results (list of lists structure).
            
            - Format: [[row1, row2, ...], [row1, row2, ...], ...]
            - Outer list: One element per query execution (one per record)
            - Inner lists: Rows returned by each query
            - Each row is a dict with column names as keys
            
            **Important**: Always access results with results[query_index][row_index]
            For single query (one record), use results[0] to get the row list.
        
        Raises:
            ValueError: If table not set or parameter keys don't match schema
            RuntimeError: If pool not started or query execution fails
        
        Example:
            ```python
            # Query without parameters
            index.set_current_table("users")
            results = await index.run_queries(
                "SELECT * FROM {dataset_table_id} LIMIT 10"
            )
            for row in results[0]:  # Access first (and only) query result
                print(row['email'])
            
            # Query with single parameter
            results = await index.run_queries(
                "SELECT * FROM {dataset_table_id} WHERE email = @email",
                records=[{"email": "user@example.com"}]
            )
            if results and results[0]:  # Check if results exist
                user_id = results[0][0]['id']  # Get first row of first query
            
            # Query with multiple parameter sets (parallel execution)
            results = await index.run_queries(
                "SELECT * FROM {dataset_table_id} WHERE id = @id",
                records=[
                    {"id": "user-123"},
                    {"id": "user-456"},
                    {"id": "user-789"}
                ]
            )
            # results[0] = rows for user-123
            # results[1] = rows for user-456
            # results[2] = rows for user-789
            
            # Aggregate query
            results = await index.run_queries(
                "SELECT MAX(`order`) as max_order FROM {dataset_table_id} WHERE conversation_id = @conversation_id",
                records=[{"conversation_id": "conv-123"}]
            )
            max_order = results[0][0]['max_order'] if results and results[0] else None
            ```
        
        Note:
            - Requires set_current_table() to be called first
            - Parameter types are validated against the table schema
            - Multiple records are executed in parallel across pool workers
            - {dataset_table_id} is automatically replaced with the current table path
            - Always returns list of lists, even for single query
        """
        query_template = base_query.format(dataset_table_id=self.table_info.query_path)
        job_configs = []
        if records:
            for record in records:
                job_config = self._build_query_parameters(record)
                job_configs.append(job_config)
               
            queries = [query_template] * len(job_configs) 
            res = await self.client_pool.run_query(queries, job_configs=job_configs)
        else:
            res = await self.client_pool.run_query([query_template])
        return res

    async def async_update_records(self, base_query: str, records: List[Dict[str, Any]]) -> None:
        """
        Async update records using a base query template.
        
        Args:
            base_query: Query template with {dataset_table_id} placeholder
            records: List of record dictionaries with update data
        """
        self._validate_table_set()
        
        start_time = time.time()
        num_records = len(records)
        logger.info(f"🔄 Async updating {num_records} record(s) in {self.table_info.table_name}...")
        
        await self.run_queries(base_query, records)
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Async updated {num_records} record(s) in {elapsed:.3f}s (avg: {elapsed/num_records:.3f}s per record)")

    
    def delete_records(self, base_query: str, records: List[Dict[str, Any]]) -> None:
        """
        Delete records using a base query template.
        
        Args:
            base_query: Query template with {dataset_table_id} placeholder
            records: List of record dictionaries with deletion criteria
        """
        self._validate_table_set()
        
        start_time = time.time()
        num_records = len(records)
        logger.info(f"🗑️  Deleting {num_records} record(s) from {self.table_info.table_name}...")
        
        query_template = base_query.format(dataset_table_id=self.table_info.query_path)
        
        for idx, record in enumerate(records, 1):
            try:
                job_config = self._build_query_parameters(record)                
                query_job = self.client.query(query_template, job_config=job_config)
                query_job.result()
                
                if idx % 10 == 0 or idx == num_records:
                    logger.debug(f"   Progress: {idx}/{num_records} records deleted")
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"❌ Failed to delete record {idx}/{num_records} after {elapsed:.3f}s: {e}")
                raise RuntimeError(f"Failed to delete record {record}: {e}")
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Deleted {num_records} record(s) in {elapsed:.3f}s")
    
    async def async_delete_records(self, base_query: str, records: List[Dict[str, Any]]) -> None:
        """
        Async delete records using a base query template.
        
        Args:
            base_query: Query template with {dataset_table_id} placeholder
            records: List of record dictionaries with deletion criteria
        """
        self._validate_table_set()
        
        start_time = time.time()
        num_records = len(records)
        logger.info(f"🗑️  Async deleting {num_records} record(s) from {self.table_info.table_name}...")
        
        await self.run_queries(base_query, records)
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Async deleted {num_records} record(s) in {elapsed:.3f}s")

    def start_pool(self) -> None:
        if not self.client_pool._running:
            logger.info(f"🚀 Starting pool for {self.proj_id}")
            self.client_pool.start()
        else:
            logger.debug(f"⏭️  Pool already running for {self.proj_id}")

    def stop_pool(self) -> None:
        """Stop the pool only if this index owns it."""
        if self._owns_pool:
            logger.info(f"🛑 Stopping dedicated pool for {self.proj_id}")
            self.client_pool.stop()
        else:
            logger.debug(f"⏭️  Skipping stop for shared pool (managed by pool manager)")

