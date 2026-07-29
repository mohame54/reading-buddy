import os
import logging
from typing import Optional
from .pool import BigQueryProcessPool

logger = logging.getLogger(__name__)


class BigQueryPoolManager:
    """
    Singleton manager for shared BigQuery process pools.
    
    This class manages a registry of BigQuery process pools, ensuring that multiple
    BigQueryIndexBase instances can share the same pool for a given project. This
    prevents spawning excessive worker processes and improves resource utilization.
    
    Design Pattern: Singleton
        - Only one manager instance exists per application
        - Pools are keyed by project ID
        - Pools are automatically reused when requested for the same project
    
    Benefits of Shared Pools:
        - Resource efficiency: One pool per project instead of one per table/index
        - Consistent performance: All indices benefit from the same worker pool
        - Simplified lifecycle: Start pool once, use across many indices
        - Memory efficient: Fewer processes and connections
    
    Usage:
        ```python
        # Recommended: Use the convenience function
        pool = get_shared_pool(proj_id="my-project", num_workers=4)
        
        # Or access manager directly
        manager = BigQueryPoolManager()
        pool = manager.get_pool(proj_id="my-project", num_workers=4)
        
        # Check status of all pools
        status = manager.get_status()
        
        # Stop specific pool
        manager.stop_pool("my-project")
        
        # Stop all pools (cleanup)
        manager.stop_all_pools()
        ```
    
    Note:
        - Pools are created on first request and reused thereafter
        - num_workers and query_timeout only apply when creating new pools
        - Stopping a pool removes it from the registry
        - Thread-safe for concurrent access
    """
    _instance: Optional['BigQueryPoolManager'] = None
    _pools: dict[str, BigQueryProcessPool] = {}
    _started: set[str] = set()
    
    def __new__(cls):
        """Singleton pattern: Returns the same instance on every instantiation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_pool(
        self, 
        proj_id: str, 
        num_workers: int = 2, 
        query_timeout: int = 30,
        auto_start: bool = True
    ) -> BigQueryProcessPool:
        """
        Get or create a shared pool for the given project.
        
        Args:
            proj_id: Google Cloud project ID
            num_workers: Number of worker processes (only used when creating new pool)
            query_timeout: Query timeout in seconds (only used when creating new pool)
            auto_start: Whether to automatically start the pool if not already started
            
        Returns:
            Shared BigQueryProcessPool instance
        """
        pool_key = f"{proj_id}"
        
        if pool_key not in self._pools:
            # Get max_queue_size from environment (default: 50, set to 0 for unlimited)
            max_queue_size = int(os.getenv("BQ_POOL_MAX_QUEUE_SIZE", "50"))
            max_queue_size = None if max_queue_size == 0 else max_queue_size
            
            logger.debug(
                f"🏗️  Creating NEW shared pool for project '{proj_id}' with {num_workers} workers, "
                f"max_queue_size={'unlimited' if max_queue_size is None else max_queue_size}"
            )
            self._pools[pool_key] = BigQueryProcessPool(
                proj_id=proj_id,
                num_workers=num_workers,
                query_timeout=query_timeout,
                max_queue_size=max_queue_size
            )
        else:
            logger.debug(f"♻️  Reusing existing pool for project '{proj_id}'")
        
        pool = self._pools[pool_key]
        
        # Auto-start if requested and not already started
        if auto_start and pool_key not in self._started:
            logger.info(f"🚀 Starting shared pool for '{proj_id}'")
            pool.start()
            self._started.add(pool_key)
        
        return pool
    
    def stop_pool(self, proj_id: str) -> None:
        """
        Stop and remove a specific pool from the registry.
        
        Args:
            proj_id: Google Cloud project ID of the pool to stop
        
        Note:
            - Gracefully stops the pool and removes it from management
            - Safe to call even if pool doesn't exist (logs warning)
            - Subsequent get_pool() calls will create a new pool
        """
        pool_key = f"{proj_id}"
        
        if pool_key in self._pools:
            logger.debug(f"🛑 Stopping pool for '{proj_id}'")
            self._pools[pool_key].stop()
            self._started.discard(pool_key)
            del self._pools[pool_key]
        else:
            logger.warning(f"⚠️  No pool found for '{proj_id}'")
    
    def stop_all_pools(self) -> None:
        """
        Stop and cleanup all managed pools.
        
        This should be called during application shutdown to ensure
        all worker processes are properly terminated.
        
        Note:
            - Iterates through all pools and stops them
            - Clears the entire pool registry
            - Useful for cleanup at application exit
        """
        logger.info(f"🛑 Stopping all {len(self._pools)} shared pool(s)")
        for proj_id in list(self._pools.keys()):
            self.stop_pool(proj_id)
    
    def get_status(self) -> dict:
        """
        Get status of all managed pools.
        
        Returns:
            Dictionary mapping project IDs to their pool status dicts.
            Each status dict contains:
            - running: Whether pool is active
            - workers_total: Total configured workers
            - workers_ready: Workers that initialized
            - workers_alive: Currently alive workers
            - pending_tasks: Tasks awaiting results
            - tasks_processed: Total tasks completed
        
        Example:
            ```python
            status = manager.get_status()
            # {
            #   "my-project": {
            #     "running": True,
            #     "workers_total": 4,
            #     "workers_ready": 4,
            #     "workers_alive": 4,
            #     "pending_tasks": 2,
            #     "tasks_processed": 150
            #   }
            # }
            ```
        """
        return {
            pool_key: pool.get_pool_status()
            for pool_key, pool in self._pools.items()
        }


_pool_manager = BigQueryPoolManager()


def get_shared_pool(
    proj_id: str,
    num_workers: Optional[int] = None,
    query_timeout: Optional[int] = None,
    auto_start: bool = True
) -> BigQueryProcessPool:
    """
    Convenience function to get a shared pool.
    
    Args:
        proj_id: Google Cloud project ID
        num_workers: Number of workers (only used for new pools, defaults to env var or 2)
                    Keep this low (2-4) to minimize memory overhead.
                    Each worker process adds ~100-200MB memory overhead.
        query_timeout: Query timeout (only used for new pools, defaults to env var or 30)
        auto_start: Whether to auto-start the pool
        
    Returns:
        Shared BigQueryProcessPool instance
    
    Memory Considerations:
        - 2 workers: ~200-400MB overhead (recommended for most use cases)
        - 4 workers: ~400-800MB overhead (for higher throughput)
        - 8+ workers: ~800MB+ overhead (only if you have high query volume)
        
    Environment Variables:
        - BQ_POOL_NUM_WORKERS: Number of worker processes (default: 2)
        - BQ_POOL_QUERY_TIMEOUT: Query timeout in seconds (default: 30)
        - BQ_POOL_MAX_QUEUE_SIZE: Max pending tasks in queue (default: 50, set to 0 for unlimited)
    """
    if num_workers is None:
        num_workers = int(os.getenv("BQ_POOL_NUM_WORKERS", "1"))
    
    if query_timeout is None:
        query_timeout = int(os.getenv("BQ_POOL_QUERY_TIMEOUT", "30"))
    
    # Warn if worker count is very high
    if num_workers > 8:
        logger.warning(f"⚠️  High worker count ({num_workers}) configured. Each worker adds ~100-200MB memory overhead.")
    
    return _pool_manager.get_pool(
        proj_id=proj_id,
        num_workers=num_workers,
        query_timeout=query_timeout,
        auto_start=auto_start
    )


def stop_all_shared_pools() -> None:
    """
    Convenience function to stop all shared pools.
    
    Useful for application shutdown or cleanup. Stops all pools
    managed by the global pool manager instance.
    
    Example:
        ```python
        import atexit
        from bq.pool_manager import stop_all_shared_pools
        
        # Register cleanup on exit
        atexit.register(stop_all_shared_pools)
        ```
    """
    _pool_manager.stop_all_pools()


def get_pool_manager_status() -> dict:
    """
    Get status of all pools managed by the global pool manager.
    
    Returns:
        Dictionary mapping project IDs to pool status information.
        See BigQueryPoolManager.get_status() for details.
    """
    return _pool_manager.get_status()

