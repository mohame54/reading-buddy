import os
import time
import logging
from typing import List, Optional, Literal, Dict, Any
from vertexai.language_models import TextEmbeddingModel
from src.config import get_settings
from .indices import BQEmbeddingIndex
from .utils import get_gemini_embeds, setup_vertex_ai
from .queries import VEC_SEARCH_QUERY, VEC_SEARCH_QUERY_CONDITIONED
from .rag_config import resolve_embedding_dim

logger = logging.getLogger(__name__)


class BQTextEmbeddingIndex(BQEmbeddingIndex):

    def __init__(
        self,
        proj_dataset_id: str,
        txt_model_name: str,
        schema_key: Optional[str] = None,
        schema_path: Optional[str] = None,
        embedding_column: Optional[str] = "embedding",
        txt_embd_dim: Optional[int] = None,
        pool_num_workers: Optional[int] = None,
        pool_query_timeout_secs: Optional[int] = None,
        use_shared_pool: Optional[bool] = True
    ):
        """
        Initialize BQTextEmbeddingIndex with text embedding configuration.
        
        Args:
            proj_dataset_id: Project and dataset ID in format 'project.dataset'
            txt_model_name: Name of the text embedding model to use
            schema_key: Key to use in schema JSON file
            schema_path: Path to schema JSON file
            embedding_column: Name of the text embedding column
            txt_embd_dim: Text embedding dimension (optional)
            pool_num_workers: Number of workers for pool (only used if not using shared pool)
            pool_query_timeout_secs: Query timeout in seconds
            use_shared_pool: If True, uses a shared pool across all indices (recommended)
        """
        start_time = time.time()
        logger.info(f"🤖 Initializing Text Embedding Index with model: {txt_model_name}")
        if pool_num_workers is None:
            pool_num_workers = get_settings().bq_pool_num_workers
        super().__init__(
            proj_dataset_id=proj_dataset_id,
            schema_key=schema_key,
            schema_path=schema_path,
            embedding_column=embedding_column,
            embedding_dim=txt_embd_dim,
            pool_num_workers=pool_num_workers,
            pool_query_timeout_secs=pool_query_timeout_secs,
            use_shared_pool=use_shared_pool
        )

        self.txt_model_name = txt_model_name

        # Initialize text embedding model
        creds_base64 = os.getenv("GOOGLE_CREDENTIALS")
        logger.info(f"🔍 Using text embedding model: {txt_model_name}")
        self.txt_model = TextEmbeddingModel.from_pretrained(txt_model_name)
        setup_vertex_ai(creds_base64, self.proj_id, from_b64=True)
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Text Embedding Index initialized in {elapsed:.3f}s")

    def set_current_table(self, table_name: str, prefix: Optional[str] = None) -> None:
        super().set_current_table(table_name, prefix)
        if self.embedding_dim is not None:
            return
        self.embedding_dim = resolve_embedding_dim(
            self.client,
            self.table_info.query_path,
            self.embedding_column,
            self.txt_model_name,
        )
        if self.embedding_dim is not None:
            logger.info(
                "Query embeddings will use dimension %s for table %s",
                self.embedding_dim,
                self.table_info.table_name,
            )

    def get_embeddings(
        self,
        contents: List[str],
        batch_size: Optional[int] = None,
        poll_time: Optional[int] = 0,
        chunk_size: Optional[int] = 1000,
        max_toks_request_size: Optional[int] = 20000,
        task: Literal["RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT"] = "RETRIEVAL_DOCUMENT",
        **embedding_kwargs,
    ) -> List[List[float]]:
        """
        Generate text embeddings using Gemini model.
        
        Args:
            contents: List of text strings to embed
            batch_size: Batch size for processing
            poll_time: Time to wait between polling requests
            chunk_size: Size of text chunks
            max_toks_request_size: Maximum tokens per request
            task: Type of task (RETRIEVAL_QUERY or RETRIEVAL_DOCUMENT)
            **embedding_kwargs: Additional keyword arguments
            
        Returns:
            List of embedding vectors
        """

        return get_gemini_embeds(
            model=self.txt_model,
            contents=contents,
            dim=self.embedding_dim,
            chunk_size=chunk_size,
            max_toks_request_size=max_toks_request_size,
            batch_size=batch_size,
            poll_time=poll_time,
            task=task,
        )

    async def async_rag(
        self,
        queries: List[str],
        topk:Optional[int] = 3,
        select_data: Optional[List[str]] = None,
        conditions: Optional[List[Dict[str, Any]]] = None,
        max_timeout: Optional[int] = 20
    ):
        """
        Execute asynchronous Retrieval-Augmented Generation (RAG) queries.
        
        This method performs semantic search on embeddings stored in BigQuery by:
        1. Converting input queries to embeddings using the text embedding model
        2. Executing vector search queries to retrieve top-k similar documents
        3. Returning the search results with specified data columns
        
        Args:
            queries: List of text queries to embed and search for
            topk: Number of top results to return per query (default: 3)
            select_data: List of column names to include in results. If None, defaults to 
                        DEFAULT_EMBEDDING_CHUNK_COLUMN (default: None)
            max_timeout: Maximum timeout in seconds for async query execution (default: 20)
            
        Returns:
            List of search results containing the top-k matches for each query,
            with the specified columns from select_data included in each result
            
        Raises:
            Exception: If query execution exceeds max_timeout or if embedding generation fails
            
        Notes:
            - Column names in select_data are automatically qualified with 'base.' prefix
            - Execution time is logged separately for embedding generation and query execution
            - Uses VECTOR_SEARCH_QUERY template with dynamically injected parameters
        """
        start_time = time.time()
        num_queries = len(queries)
        logger.info(f"🔍 Starting RAG query with {num_queries} quer{'y' if num_queries == 1 else 'ies'}, topk={topk}")
        
        if not select_data:
            select_data = [self.DEFAULT_EMBEDDING_CHUNK_COLUMN]
        else:
            select_data = [str(data) for data in select_data]
        
        # Qualify columns with 'base.' prefix for VECTOR_SEARCH
        qualified_columns = [f"base.{col}" for col in select_data]
        select_data_statement = ",".join(qualified_columns)
        db_queries = []
        for idx, query in enumerate(queries):
            attrs_kwargs = {
                "select_data":select_data_statement,
                "dataset_table_id":self.table_info.query_path,
                "embd_name":self.embedding_column,
                "topk":topk
            }
            db_query = VEC_SEARCH_QUERY
            if conditions and len(conditions) > idx and len(conditions[idx]):
                condition = conditions[idx]
                db_query = VEC_SEARCH_QUERY_CONDITIONED
                condition_statment = self.decode_conditions_dict(condition)
                attrs_kwargs.update(
                   {"condition": condition_statment}
                )

            for attr, v in attrs_kwargs.items():
                db_query = db_query.replace(f"{{{attr}}}", str(v))
            
            db_queries.append(db_query)

        logger.debug(f"DB Query: {db_query}")
        
        # Generate query embeddings
        embd_start = time.time()
        logger.debug(f"🔢 Generating query embeddings for {num_queries} quer{'y' if num_queries == 1 else 'ies'}...")
        embeddings = self.get_embeddings(queries, task="RETRIEVAL_QUERY")
        embd_elapsed = time.time() - embd_start
        logger.debug(f"✅ Query embeddings generated in {embd_elapsed:.3f}s")
        
        # Execute RAG queries
        res = await self.async_embd_query(db_queries, embeddings, max_timeout=max_timeout)
        
        total_elapsed = time.time() - start_time
        logger.info(f"✅ RAG query completed in {total_elapsed:.3f}s (embedding: {embd_elapsed:.3f}s, query: {total_elapsed-embd_elapsed:.3f}s)")
        
        return res

    def decode_conditions_dict(self, conditions):
        conditions_statements = []
        for k, v in conditions.items():
            if isinstance(v, str):
                v = f"'{v}'"
            conditions_statements.append(f"{k}={v}")
        conds = " AND ".join(conditions_statements)

        return conds
