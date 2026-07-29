import os
import uuid
import asyncio
import logging
import threading
import queue
import time
from typing import Optional
from multiprocessing import Process, Queue

from src.config import get_settings
from .process_work_loop import worker_loop


class BigQueryProcessPool:
    """
    Process-based pool for executing BigQuery queries asynchronously.
    
    This class manages a pool of worker processes that execute BigQuery queries in parallel.
    Each worker runs in a separate process with its own BigQuery client, enabling true
    parallel query execution without GIL limitations.
    
    Architecture:
        - Main process: Manages task distribution and result collection
        - Worker processes: Execute BigQuery queries independently
        - Task queue: Distributes work to available workers
        - Result queue: Collects results from workers
        - Result dispatcher: Background thread that routes results to pending futures
    
    Features:
        - Parallel query execution across multiple processes
        - Automatic worker health monitoring and recovery
        - Configurable timeouts and worker counts
        - Graceful shutdown with worker cleanup
        - Support for parameterized queries via QueryJobConfig
        - Query distribution modes (parallel vs batch)
    
    Usage:
        ```python
        # Create and start pool
        pool = BigQueryProcessPool(proj_id="my-project", num_workers=4)
        pool.start()
        
        # Execute queries
        results = await pool.run_query(["SELECT * FROM table LIMIT 10"])
        
        # Stop pool when done
        pool.stop()
        ```
    
    Note:
        - Call start() before executing queries
        - Call stop() to cleanup resources when done
        - For shared pools across multiple tables, use pool_manager.get_shared_pool()
    """
    
    def __init__(self,proj_id:str, num_workers: Optional[int] = None, query_timeout: Optional[int] = None, max_queue_size: Optional[int] = None):
        """
        Initialize BigQuery process pool.
        
        Args:
            proj_id: Google Cloud project ID for BigQuery operations
            num_workers: Number of worker processes to spawn (default: `BQ_POOL_NUM_WORKERS` or 1)
            query_timeout: Default timeout for queries in seconds (default: `BQ_POOL_QUERY_TIMEOUT` or 30)
            max_queue_size: Maximum number of tasks in queue (None = unlimited, helps prevent memory buildup)
        
        Note:
            - Keep num_workers low (2-4) unless you have high query throughput
            - Each worker process adds ~100-200MB of memory overhead
            - Large result sets are loaded into memory, consider using LIMIT clauses
        """
        settings = get_settings()
        if num_workers is None:
            num_workers = settings.bq_pool_num_workers
        if query_timeout is None:
            query_timeout = settings.bq_pool_query_timeout
        if max_queue_size is None:
            max_queue_size = settings.bq_pool_max_queue_size
        self.num_workers = num_workers
        self.query_timeout = query_timeout
        self.max_queue_size = max_queue_size
        self.task_queue = Queue(maxsize=max_queue_size) if max_queue_size else Queue()
        self.result_queue = Queue()
        self.stop_signal = Queue()
        self.worker_ready_queue = Queue()  # New: for worker readiness signaling
        self.workers = []
        self.logger = logging.getLogger("BQPool")
        self._pending_futures = {}
        self._running = False
        self.proj_id = proj_id
        self._task_counter = 0
        self._workers_ready = 0
        self._completed_tasks = 0  # Track completed tasks for memory monitoring

    def start(self):
        """
        Start the pool by spawning worker processes and result dispatcher.
        
        This method:
        1. Spawns worker processes
        2. Starts result dispatcher thread
        3. Waits for workers to initialize (with 10s timeout)
        
        Idempotent: Safe to call multiple times (no-op if already started)
        
        Raises:
            Logs error if workers fail to initialize within timeout
        """
        if self._running: return
        self._running = True
        self.logger.info(f"🚀 Starting BigQuery process pool with {self.num_workers} worker(s)")
        
        # Spawn workers
        for i in range(self.num_workers): 
            self._spawn_worker(i)
        
        # Start result dispatcher thread
        threading.Thread(target=self._result_dispatcher, daemon=True).start()
        
        # Wait for workers to be ready (with timeout)
        self.logger.info(f"⏳ Waiting for {self.num_workers} worker(s) to initialize...")
        ready_timeout = get_settings().bq_pool_ready_timeout
        start_wait = time.time()
        
        while self._workers_ready < self.num_workers:
            elapsed = time.time() - start_wait
            if elapsed > ready_timeout:
                self.logger.error(f"❌ Timeout waiting for workers! Only {self._workers_ready}/{self.num_workers} ready")
                break
            
            try:
                worker_id = self.worker_ready_queue.get(timeout=0.1)
                self._workers_ready += 1
                self.logger.info(f"✅ Worker {worker_id} ready ({self._workers_ready}/{self.num_workers})")
            except queue.Empty:
                continue
        
        if self._workers_ready == self.num_workers:
            self.logger.info(f"✅ All {self.num_workers} worker(s) ready!")
        else:
            self.logger.warning(f"⚠️ Only {self._workers_ready}/{self.num_workers} workers ready. Some workers may have failed to start.")

    def stop(self):
        """
        Stop the pool and cleanup all resources.
        
        This method:
        1. Stops the result dispatcher thread
        2. Sends stop signals to all workers
        3. Waits for graceful worker shutdown (2s timeout per worker)
        4. Forcefully terminates any remaining workers
        
        Safe to call even if pool not running.
        """
        if not self._running:
            return
        
        self.logger.info("🛑 Shutting down BigQuery pool...")
        self._running = False # Stops the dispatcher loop

        for _ in self.workers:
            self.stop_signal.put("STOP")

        # Join workers
        terminated = 0
        for p in self.workers:
            p.join(timeout=2)
            if p.is_alive():
                p.terminate()
                terminated += 1
        
        if terminated > 0:
            self.logger.warning(f"⚠️ Forcefully terminated {terminated} worker(s)")
        
        self.workers.clear()
        self.logger.info(f"✅ Pool shutdown complete. Processed {self._task_counter} total tasks")

    def get_pool_status(self):
        """
        Get current pool status and health metrics.
        
        Returns:
            Dictionary containing:
            - running: Whether pool is currently active
            - workers_total: Total number of configured workers
            - workers_ready: Number of workers that completed initialization
            - workers_alive: Number of workers currently alive
            - pending_tasks: Number of tasks waiting for results
            - tasks_processed: Total tasks submitted since pool start
            - tasks_completed: Total tasks successfully completed
            - max_queue_size: Maximum queue size (None if unlimited)
        """
        alive_workers = sum(1 for p in self.workers if p.is_alive())
        
        # Try to get queue sizes (not supported on macOS)
        try:
            task_queue_size = self.task_queue.qsize()
            result_queue_size = self.result_queue.qsize()
        except (NotImplementedError, AttributeError):
            task_queue_size = 'N/A'
            result_queue_size = 'N/A'
        
        return {
            "running": self._running,
            "workers_total": self.num_workers,
            "workers_ready": self._workers_ready,
            "workers_alive": alive_workers,
            "pending_tasks": len(self._pending_futures),
            "tasks_processed": self._task_counter,
            "tasks_completed": self._completed_tasks,
            "task_queue_size": task_queue_size,
            "result_queue_size": result_queue_size,
            "max_queue_size": self.max_queue_size
        }
    
    def _check_worker_health(self):
        """Check if workers are alive and healthy"""
        dead_workers = []
        for i, p in enumerate(self.workers):
            if not p.is_alive():
                dead_workers.append(i)
        
        if dead_workers:
            self.logger.error(f"❌ Found {len(dead_workers)} dead worker(s): {dead_workers}")
            return False
        return True
    
    def cleanup_completed_tasks(self) -> int:
        """
        Force cleanup of any completed tasks to free memory.
        
        Returns:
            Number of tasks cleaned up
        
        Note:
            Normally cleanup happens automatically, but this can be called
            manually if you suspect memory buildup.
        """
        cleanup_count = 0
        for task_id, fut in list(self._pending_futures.items()):
            if fut.done():
                del self._pending_futures[task_id]
                cleanup_count += 1
        
        if cleanup_count > 0:
            self.logger.info(f"🧹 Cleaned up {cleanup_count} completed task(s)")
        
        return cleanup_count

    async def _submit_task(self, task_id: str, queries: list, job_configs: list, timeout: int) -> None:
        put_timeout = get_settings().bq_pool_queue_put_timeout
        try:
            await asyncio.to_thread(
                self.task_queue.put,
                (task_id, queries, job_configs, timeout),
                True,
                put_timeout,
            )
        except queue.Full as exc:
            status = self.get_pool_status()
            self.logger.error(f"❌ BigQuery task queue is full, rejecting task {task_id[:8]}... Pool status: {status}")
            raise RuntimeError("BigQuery task queue is full; try again later") from exc

    def _spawn_worker(self, i):
        self.logger.info(f"   Spawning worker {i}...")
        p = Process(target=worker_loop, args=(i, self.proj_id, self.task_queue, self.result_queue, self.stop_signal, self.worker_ready_queue), daemon=True)
        p.start()
        self.workers.append(p)

    def _result_dispatcher(self):
        self.logger.info("📡 Result dispatcher thread started")
        while self._running:
            try:
                item = self.result_queue.get(timeout=0.5)
                task_id, result, error = item
                
                self.logger.debug(f"📨 Received result for task {task_id[:8]}...")
                
                if task_id in self._pending_futures:
                    fut = self._pending_futures.pop(task_id)
                    if not fut.cancelled():
                        loop = fut.get_loop()
                        if error:
                            self.logger.error(f"❌ Task {task_id[:8]}... failed with error")
                            loop.call_soon_threadsafe(fut.set_exception, RuntimeError(error))
                        else:
                            self.logger.debug(f"✅ Task {task_id[:8]}... completed successfully")
                            loop.call_soon_threadsafe(fut.set_result, result)
                            self._completed_tasks += 1
                            
                            # Log memory warning if pending futures building up
                            if len(self._pending_futures) > 50:
                                self.logger.warning(f"⚠️  High pending futures count: {len(self._pending_futures)}. Potential memory buildup!")
                    
                    # Explicitly delete result to free memory
                    del result
                else:
                    self.logger.warning(f"⚠️ Received result for unknown task {task_id[:8]}... (may have timed out)")
                    
            except queue.Empty: 
                continue
            except Exception as e:
                self.logger.error(f"❌ Error in result dispatcher: {e}", exc_info=True)
        
        self.logger.info("📡 Result dispatcher thread stopped")

    async def run_query(self, queries: list[str], job_configs: Optional[list] = None, timeout: int = None, distribute: bool = True):
        """
        Execute BigQuery queries asynchronously using the worker process pool.
        
        Args:
            queries: List of SQL query strings to execute
            job_configs: Optional list of BigQuery QueryJobConfig objects (one per query)
            timeout: Query timeout in seconds (defaults to pool's query_timeout)
            distribute: If True and multiple queries provided, distribute queries across 
                       workers for parallel execution. If False, send all queries as a 
                       single batch to one worker.
        
        Returns:
            List of query results. Return structure depends on distribute parameter:
            
            - If distribute=True with N queries: Returns list of N result lists
              Example: [[rows_q1], [rows_q2], ...] where each rows_qX is a list of dicts
              
            - If distribute=False: Returns list with single element containing all results
              Example: [[rows_q1, rows_q2, ...]]
            
            Each row is a dictionary with column names as keys.
            For DML queries (INSERT/UPDATE/DELETE), returns: {"status": "DML Executed", "affected": N}
        
        Raises:
            RuntimeError: If pool not started, workers unhealthy, or query execution fails
            asyncio.TimeoutError: If query execution exceeds timeout
            asyncio.CancelledError: If query execution is cancelled
        
        Example:
            ```python
            # Single query
            results = await pool.run_query(["SELECT * FROM table LIMIT 10"])
            rows = results[0]  # Get first (and only) query result
            for row in rows:
                print(row['column_name'])
            
            # Multiple queries distributed across workers
            results = await pool.run_query([
                "SELECT COUNT(*) as cnt FROM table1",
                "SELECT COUNT(*) as cnt FROM table2"
            ], distribute=True)
            
            count1 = results[0][0]['cnt']  # First query result
            count2 = results[1][0]['cnt']  # Second query result
            
            # Multiple queries with parameters
            job_configs = [
                QueryJobConfig(query_parameters=[ScalarQueryParameter("id", "STRING", "123")]),
                QueryJobConfig(query_parameters=[ScalarQueryParameter("id", "STRING", "456")])
            ]
            results = await pool.run_query([
                "SELECT * FROM table WHERE id = @id",
                "SELECT * FROM table WHERE id = @id"
            ], job_configs=job_configs, distribute=True)
            ```
        
        Note:
            - All queries always return a list of lists structure
            - Access results with results[query_index][row_index]
            - For single query, use results[0] to get the row list
            - Workers process queries in parallel when distribute=True
            - Ensure pool is started before calling this method
        """
        if not self._running: raise RuntimeError("Pool not started")
        
        # Check if enough workers are available
        if self._workers_ready == 0:
            raise RuntimeError("No workers are ready to process queries")
        
        # Check worker health
        if not self._check_worker_health():
            status = self.get_pool_status()
            self.logger.error(f"⚠️ Pool health check failed: {status}")
            raise RuntimeError(f"Worker pool unhealthy: {status['workers_alive']}/{status['workers_total']} workers alive")
        
        if distribute and len(queries) > self._workers_ready:
            self.logger.warning(f"⚠️ Distributing {len(queries)} queries but only {self._workers_ready} workers available")
        
        start_time = time.time()
        timeout = timeout or self.query_timeout
        if not job_configs:
            job_configs = [None] * len(queries)
        
        num_queries = len(queries)
        
        # If distribute=True and multiple queries, submit each as separate task
        if distribute and num_queries > 1:
            self.logger.info(f"📤 Distributing {num_queries} queries across workers, timeout={timeout}s")
            
            # Submit each query as a separate task
            loop = asyncio.get_running_loop()
            futures = []
            
            for idx, (query, job_config) in enumerate(zip(queries, job_configs)):
                task_id = str(uuid.uuid4())
                self._task_counter += 1
                
                future = loop.create_future()
                self._pending_futures[task_id] = future
                futures.append(future)
                
                try:
                    await self._submit_task(task_id, [query], [job_config], timeout)
                except RuntimeError:
                    for pending_task_id, pending_future in list(self._pending_futures.items()):
                        if pending_future in futures and not pending_future.done():
                            pending_future.cancel()
                            del self._pending_futures[pending_task_id]
                    raise
                self.logger.debug(f"   Submitted query {idx+1}/{num_queries} as task {task_id[:8]}...")
            
            # Log queue status (qsize() not supported on macOS)
            try:
                queue_size = self.task_queue.qsize()
            except (NotImplementedError, AttributeError):
                queue_size = 'N/A'
            self.logger.debug(f"📊 Task queue size: ~{queue_size}, Pending futures: {len(self._pending_futures)}")
            try:
                # Add timeout wrapper around gather
                results = await asyncio.wait_for(
                    asyncio.gather(*futures),
                    timeout=timeout + 5  # Add 5 seconds buffer
                )
                self.logger.debug(f"📦 Received {len(results)} results from workers")
                
                # Flatten results (each result is a list with one item)
                try:
                    flattened = [item for sublist in results for item in sublist]
                except Exception as flatten_err:
                    self.logger.error(f"❌ Error flattening results: {flatten_err}")
                    self.logger.error(f"   Results structure: {[type(r) for r in results]}")
                    raise RuntimeError(f"Failed to flatten distributed query results: {flatten_err}")
                
                elapsed = time.time() - start_time
                self.logger.info(f"✅ All {num_queries} distributed queries completed in {elapsed:.3f}s")
                return flattened
            except asyncio.TimeoutError:
                # Cancel all pending futures
                cancelled_count = 0
                for task_id, fut in list(self._pending_futures.items()):
                    if fut in futures and not fut.done():
                        fut.cancel()
                        del self._pending_futures[task_id]
                        cancelled_count += 1
                elapsed = time.time() - start_time
                self.logger.error(f"❌ Distributed queries timed out after {elapsed:.3f}s (cancelled {cancelled_count} tasks)")
                raise RuntimeError(f"Query execution timed out after {timeout + 5}s")
            except asyncio.CancelledError:
                # Cancel all pending futures
                for task_id, fut in list(self._pending_futures.items()):
                    if fut in futures and not fut.done():
                        fut.cancel()
                        del self._pending_futures[task_id]
                self.logger.warning(f"⚠️ Distributed queries were cancelled")
                raise
            except Exception as e:
                elapsed = time.time() - start_time
                self.logger.error(f"❌ Distributed queries failed after {elapsed:.3f}s: {e}")
                raise
        else:
            # Original behavior: submit all queries as single task
            task_id = str(uuid.uuid4())
            self._task_counter += 1
            self.logger.info(f"📤 Submitting task {task_id[:8]}... with {num_queries} quer{'y' if num_queries == 1 else 'ies'}, timeout={timeout}s")
            
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            self._pending_futures[task_id] = future

            try:
                await self._submit_task(task_id, queries, job_configs, timeout)
            except RuntimeError:
                self._pending_futures.pop(task_id, None)
                future.cancel()
                raise

            try:
                result = await future
                elapsed = time.time() - start_time
                self.logger.info(f"✅ Task {task_id[:8]}... completed in {elapsed:.3f}s")
                return result
            except asyncio.CancelledError:
                if task_id in self._pending_futures: del self._pending_futures[task_id]
                self.logger.warning(f"⚠️ Task {task_id[:8]}... was cancelled")
                raise
            except Exception as e:
                elapsed = time.time() - start_time
                self.logger.error(f"❌ Task {task_id[:8]}... failed after {elapsed:.3f}s: {e}")
                raise