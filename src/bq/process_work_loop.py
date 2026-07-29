import os
import time
import traceback
import logging
import queue
from multiprocessing import Queue
from .utils import load_bq_client


def worker_loop(worker_id: int,proj_id:str, task_queue: Queue, result_queue: Queue, stop_signal: Queue, ready_queue: Queue):
    """
    Worker process loop for executing BigQuery queries.
    
    This function runs in a separate process and continuously polls the task queue
    for BigQuery queries to execute. It initializes its own BigQuery client and
    handles query execution, result collection, and error reporting.
    
    Args:
        worker_id: Unique identifier for this worker process
        proj_id: Google Cloud project ID for BigQuery client initialization
        task_queue: Multiprocessing Queue for receiving tasks from the pool
                   Task format: (task_id, queries, job_configs, timeout)
        result_queue: Multiprocessing Queue for sending results back to pool
                     Result format: (task_id, results, error)
        stop_signal: Multiprocessing Queue for receiving shutdown signals
        ready_queue: Multiprocessing Queue for signaling worker readiness
    
    Task Structure:
        - task_id: Unique UUID string identifying the task
        - queries: List of SQL query strings to execute
        - job_configs: List of BigQuery QueryJobConfig objects (optional params)
        - timeout: Query timeout in seconds
    
    Result Structure:
        - task_id: Same UUID from the task
        - results: List of query results (list of dicts) or None if error
        - error: Error traceback string or None if successful
    
    Worker Lifecycle:
        1. Initialize BigQuery client and signal readiness
        2. Poll task_queue for new tasks (0.5s timeout)
        3. Execute all queries in parallel
        4. Collect and format results
        5. Send results to result_queue
        6. Repeat until stop signal received
    
    Query Results:
        - SELECT queries: List of dicts, one per row
        - DML queries (INSERT/UPDATE/DELETE): {"status": "DML Executed", "affected": N}
    
    Note:
        - Each worker runs in its own process with isolated BigQuery client
        - Workers execute multiple queries per task in parallel
        - Logs are prefixed with worker ID for debugging
        - Worker exits gracefully on stop signal or client init failure
    """
    # Setup Logging
    logging.basicConfig(
        level=logging.INFO, 
        format=f'%(asctime)s - [Worker-{worker_id}] - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(f"BQ-Worker-{worker_id}")

    logger.info(f"🚀 Worker {worker_id} starting up...")
    
    client = None
    try:
        init_start = time.time()
        creds_info = os.environ["GOOGLE_CREDENTIALS"]
        client  = load_bq_client(creds_info, proj_id, from_b64=True, force_new=True)
        init_elapsed = time.time() - init_start
        logger.info(f"✅ Worker {worker_id} initialized BQ client in {init_elapsed:.3f}s")
        
        # Signal that this worker is ready
        ready_queue.put(worker_id)
        
    except Exception as e:
        logger.error(f"❌ Worker {worker_id} failed to initialize BQ Client: {e}")
        return

    task_count = 0
    logger.info(f"👷 Worker {worker_id} ready to process tasks")
    
    while True:
        if not stop_signal.empty():
            logger.info(f"🛑 Worker {worker_id} received stop signal. Processed {task_count} total tasks")
            break

        try:
            # Get task from queue
            task = task_queue.get(timeout=0.5)
            task_count += 1
        except queue.Empty:
            continue

        # Unpack the new protocol
        # task_type should be 'SQL' or 'INSERT_JSON'
        task_id, queries, job_configs, timeout = task
        
        results = []
        num_queries = len(queries) if isinstance(queries, list) else 1
        logger.info(f"📥 Task {task_id[:8]}... received with {num_queries} quer{'y' if num_queries == 1 else 'ies'} (timeout={timeout}s)")
        if not isinstance(queries, list):
            queries = [queries]

        if not isinstance(job_configs, list):
            job_configs = [job_configs]
        try:
            start_time = time.time()
            
            # Submit all queries in parallel
            jobs = []
            for idx, (q, job_config) in enumerate(zip(queries, job_configs), 1):
                try:
                    query_start = time.time()
                    job = client.query(q, job_config=job_config)
                    jobs.append((idx, job, query_start))
                except Exception as e:
                    logger.error(f"❌ Error submitting query {idx}: {str(e)[:100]}")
                    logger.debug(f"Query content: {q[:200]}...")
                    logger.debug(f"Job config: {job_config}")
                    raise RuntimeError(f"Failed to submit query {idx}/{num_queries}: {e}")
            
            logger.debug(f"✅ Submitted {len(jobs)} job(s) to BigQuery")
            
            # Wait for all results
            for idx, job, query_start in jobs:
                try:
                    job_iter = job.result(timeout=timeout)
                    query_elapsed = time.time() - query_start
                    
                    if job.statement_type in ('INSERT', 'UPDATE', 'DELETE', 'MERGE'):
                        rows = {"status": "DML Executed", "affected": job.num_dml_affected_rows}
                        logger.debug(f"   Query {idx}/{num_queries}: {job.statement_type} affected {job.num_dml_affected_rows} row(s) in {query_elapsed:.3f}s")
                    else:
                        # Convert to list of dicts (Warning: Do not select Vector columns here)
                        # Memory optimization: Convert rows lazily and log memory warnings
                        rows = [dict(row) for row in job_iter]
                        row_count = len(rows)
                        logger.debug(f"   Query {idx}/{num_queries}: SELECT returned {row_count} row(s) in {query_elapsed:.3f}s")
                        
                        # Warn if result set is very large (potential memory issue)
                        if row_count > 10000:
                            logger.warning(f"⚠️  Large result set: {row_count} rows (~{row_count * 0.001:.1f}MB estimated). Consider using LIMIT or pagination.")
                        elif row_count > 50000:
                            logger.error(f"❌ Very large result set: {row_count} rows (~{row_count * 0.001:.1f}MB estimated). This may cause memory issues!")
                
                    results.append(rows)
                except Exception as e:
                    logger.error(f"❌ Error getting results for query {idx}: {str(e)[:100]}")
                    raise RuntimeError(f"Failed to get results for query {idx}/{num_queries}: {e}")
            
            elapsed = time.time() - start_time
            logger.info(f"✅ Task {task_id[:8]}... completed in {elapsed:.3f}s (avg: {elapsed/num_queries:.3f}s per query)")

            result_queue.put((task_id, results, None))

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ Task {task_id[:8]}... failed after {elapsed:.3f}s: {str(e)[:200]}")
            logger.debug(f"Full error trace:", exc_info=True)
            result_queue.put((task_id, None, traceback.format_exc()))
