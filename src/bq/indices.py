import time
import asyncio
import logging
from typing import List, Optional, Any
from .base import BigQueryIndexBase
from .queries import VEC_SEARCH_QUERY

logger = logging.getLogger(__name__)


class BQEmbeddingIndex(BigQueryIndexBase):
    """
    General-purpose BigQuery Embedding Index for storing and managing embeddings.
    
    This base class provides a flexible framework for working with embeddings in BigQuery.
    Subclasses should override the get_embeddings() method to implement specific
    embedding generation logic (text, image, etc.).
    
    Supports both sync and async operations.
    
    Example:
        class TextEmbeddingIndex(BQEmbeddingIndex):
            def __init__(self, proj_dataset_id, model_name, **kwargs):
                super().__init__(proj_dataset_id, **kwargs)
                self.model = TextEmbeddingModel.from_pretrained(model_name)
            
            def get_embeddings(self, contents: List[str], **kwargs) -> List[List[float]]:
                # Implement text embedding logic here
                return generate_text_embeddings(self.model, contents)
    """

    DEFAULT_SCHEMA = "schema.json"
    DEFAULT_EMBEDDING_COLUMN = "embedding"
    DEFAULT_EMBEDDING_CHUNK_COLUMN = "chunk_txt"

    def __init__(
        self,
        proj_dataset_id: str,
        schema_key: Optional[str] = None,
        schema_path: Optional[str] = None,
        embedding_column: Optional[str] = None,
        embedding_dim: Optional[int] = None,
        pool_num_workers: Optional[int] = 1,
        pool_query_timeout_secs: Optional[int] = None,
        use_shared_pool: Optional[bool] = True
    ):
        """
        Initialize BQEmbeddingIndex with configuration.
        
        Args:
            proj_dataset_id: Project and dataset ID in format 'project.dataset'
            schema_key: Key to use in schema JSON file
            schema_path: Path to schema JSON file
            embedding_column: Name of the embedding column in BigQuery table
            embedding_dim: Embedding dimension (optional, for validation/documentation)
            pool_num_workers: Number of workers for pool (only used if not using shared pool)
            pool_query_timeout_secs: Query timeout in seconds
            use_shared_pool: If True, uses a shared pool across all indices (recommended)
        """
        schema_path = schema_path or self.DEFAULT_SCHEMA

        super().__init__(proj_dataset_id, schema_path, schema_key, pool_num_workers, pool_query_timeout_secs, use_shared_pool)

        # Embedding configuration
        self.embedding_dim = embedding_dim
        self.embedding_column = embedding_column or self.DEFAULT_EMBEDDING_COLUMN

    def _validate_inputs_lengths(
        self,
        contents: List[Any],
        metadata_list: Optional[List[dict]] = None,
    ) -> None:
        """Validate that contents and metadata lists have matching lengths."""
        if metadata_list is not None and len(metadata_list) != len(contents):
            raise ValueError("metadata_list must have the same length as contents")

    def _prepare_embedding_data(
        self,
        embeddings: List[List[float]],
        metadata_list: List[dict],
    ) -> List[dict]:
        """
        Prepare data for insertion/update with embeddings.
        
        Args:
            embeddings: List of embedding vectors
            metadata_list: List of metadata dictionaries
            
        Returns:
            List of records ready for BigQuery insertion
        """
        data_records = []
        for embedding, metadata in zip(embeddings, metadata_list):
            record = {self.embedding_column: embedding}
            record.update(metadata or {})
            data_records.append(record)
        return data_records

    def get_embeddings(
        self,
        contents: List[Any],
        **embedding_kwargs,
    ) -> List[List[float]]:
        """
        Generate embeddings for the provided contents.
        
        This method MUST be overridden by subclasses to implement
        specific embedding logic (text, image, etc.).
        
        Args:
            contents: List of content items to embed (type depends on subclass)
            **embedding_kwargs: Additional keyword arguments for embedding generation
            
        Returns:
            List of embedding vectors (each vector is a List[float])
            
        Raises:
            NotImplementedError: If not overridden by subclass
            
        Example:
            def get_embeddings(self, contents: List[str], **kwargs) -> List[List[float]]:
                return [self.model.embed(text) for text in contents]
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_embeddings() method. "
            "This method should contain the logic to generate embeddings "
            "for your specific content type (text, image, etc.)."
        )

    async def async_get_embeddings(
        self,
        contents: List[Any],
        **embedding_kwargs,
    ) -> List[List[float]]:
        """
        Async: generate embeddings for the provided contents.
        
        Default implementation runs the sync get_embeddings() in a thread pool.
        Override this method in subclasses if you have a native async embedding implementation.
        
        Args:
            contents: List of content items to embed (type depends on subclass)
            **embedding_kwargs: Additional keyword arguments for embedding generation
            
        Returns:
            List of embedding vectors
            
        Example:
            async def async_get_embeddings(self, contents: List[str], **kwargs):
                return await self.model.async_embed(contents)
        """
        # Run synchronous embedding in background thread to avoid blocking event loop
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self.get_embeddings(contents, **embedding_kwargs)
        )
        return embeddings

    # -----------------------
    # Public insert/update operations
    # -----------------------
    def insert_embd_records(
        self,
        contents: List[Any],
        metadata_list: List[dict],
        **embedding_kwargs,
    ) -> None:
        """
        Insert embedding records into BigQuery table (sync).
        
        Args:
            contents: List of content items to embed and insert
            metadata_list: List of metadata dictionaries for each record
            **embedding_kwargs: Additional keyword arguments for embedding generation
        """
        self._validate_table_set()
        self._validate_inputs_lengths(contents, metadata_list)

        start_time = time.time()
        num_items = len(contents)
        logger.info(f"🔄 Generating embeddings for {num_items} item(s)...")
        
        embd_start = time.time()
        embeddings = self.get_embeddings(contents, **embedding_kwargs)
        embd_elapsed = time.time() - embd_start
        logger.info(f"✅ Generated {num_items} embedding(s) in {embd_elapsed:.3f}s (avg: {embd_elapsed/num_items:.3f}s per item)")
        
        data_records = self._prepare_embedding_data(embeddings, metadata_list)
        self.insert_records(data_records)
        
        total_elapsed = time.time() - start_time
        logger.info(f"✅ Total insert operation completed in {total_elapsed:.3f}s")

    async def async_insert_embd_records(
        self,
        contents: List[Any],
        metadata_list: List[dict],
        **embedding_kwargs,
    ) -> None:
        """
        Async insert embedding records into BigQuery table.
        
        Args:
            contents: List of content items to embed and insert
            metadata_list: List of metadata dictionaries for each record
            **embedding_kwargs: Additional keyword arguments for embedding generation
        """
        self._validate_table_set()
        self._validate_inputs_lengths(contents, metadata_list)

        start_time = time.time()
        num_items = len(contents)
        logger.info(f"🔄 Async generating embeddings for {num_items} item(s)...")
        
        embd_start = time.time()
        embeddings = await self.async_get_embeddings(contents, **embedding_kwargs)
        embd_elapsed = time.time() - embd_start
        logger.info(f"✅ Async generated {num_items} embedding(s) in {embd_elapsed:.3f}s (avg: {embd_elapsed/num_items:.3f}s per item)")
        
        data_records = self._prepare_embedding_data(embeddings, metadata_list)
        
        # Run sync insert in thread to avoid blocking event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.insert_records, data_records)
        
        total_elapsed = time.time() - start_time
        logger.info(f"✅ Total async insert operation completed in {total_elapsed:.3f}s")

    def update_embd_records(
        self,
        base_query: str,
        contents: List[Any],
        metadata_list: List[dict],
        **embedding_kwargs,
    ) -> None:
        """
        Update embedding records in BigQuery table (sync).
        
        Args:
            base_query: Query template with {dataset_table_id} placeholder
            contents: List of content items to embed and update
            metadata_list: List of metadata dictionaries for each record
            **embedding_kwargs: Additional keyword arguments for embedding generation
        """
        self._validate_table_set()
        self._validate_inputs_lengths(contents, metadata_list)

        start_time = time.time()
        num_items = len(contents)
        logger.info(f"🔄 Generating embeddings for {num_items} item(s) to update...")
        
        embd_start = time.time()
        embeddings = self.get_embeddings(contents, **embedding_kwargs)
        embd_elapsed = time.time() - embd_start
        logger.info(f"✅ Generated {num_items} embedding(s) in {embd_elapsed:.3f}s (avg: {embd_elapsed/num_items:.3f}s per item)")
        
        data_records = self._prepare_embedding_data(embeddings, metadata_list)
        self.update_records(base_query, data_records)
        
        total_elapsed = time.time() - start_time
        logger.info(f"✅ Total update operation completed in {total_elapsed:.3f}s")

    async def async_update_embd_records(
        self,
        base_query: str,
        contents: List[Any],
        metadata_list: List[dict],
        **embedding_kwargs,
    ) -> None:
        """
        Async update embedding records in BigQuery table.
        
        Args:
            base_query: Query template with {dataset_table_id} placeholder
            contents: List of content items to embed and update
            metadata_list: List of metadata dictionaries for each record
            **embedding_kwargs: Additional keyword arguments for embedding generation
        """
        self._validate_table_set()
        self._validate_inputs_lengths(contents, metadata_list)

        start_time = time.time()
        num_items = len(contents)
        logger.info(f"🔄 Async generating embeddings for {num_items} item(s) to update...")
        
        embd_start = time.time()
        embeddings = await self.async_get_embeddings(contents, **embedding_kwargs)
        embd_elapsed = time.time() - embd_start
        logger.info(f"✅ Async generated {num_items} embedding(s) in {embd_elapsed:.3f}s (avg: {embd_elapsed/num_items:.3f}s per item)")
        
        data_records = self._prepare_embedding_data(embeddings, metadata_list)
    
        await self.async_update_records(base_query, data_records)
        
        total_elapsed = time.time() - start_time
        logger.info(f"✅ Total async update operation completed in {total_elapsed:.3f}s")
        
    @property
    def embedding_column_name(self) -> str:
        """Get the name of the embedding column."""
        return self.embedding_column
    
    async def async_embd_query(
        self,
        db_queries: List[str],
        embeddings: List[List[float]],
        max_timeout: Optional[int] = 20,
        distribute: Optional[bool] = True
    ):
        start_time = time.time()
        num_queries = len(db_queries)
        logger.info(f"🔍 Executing {num_queries} embedding quer{'y' if num_queries == 1 else 'ies'}...")
        
        job_configs = [
            self._build_query_parameters({"embedding":embd})
            for embd in embeddings
        ]
        results = await self.client_pool.run_query(
            db_queries, 
            job_configs=job_configs, 
            timeout=max_timeout,
            distribute=distribute  # Distribute queries across workers
        )
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Embedding quer{'y' if num_queries == 1 else 'ies'} completed in {elapsed:.3f}s")
        
        return results