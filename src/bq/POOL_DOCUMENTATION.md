# BigQuery Process Pool Documentation

## Overview

The BigQuery Process Pool system provides efficient, parallel execution of BigQuery queries using a multi-process architecture. This system is designed to handle high-throughput query workloads while managing resources effectively.

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Index Table 1│  │ Index Table 2│  │ Index Table N│      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
          ┌──────────────────▼──────────────────────┐
          │      BigQueryPoolManager (Singleton)     │
          │  ┌────────────────────────────────────┐ │
          │  │  Project ID → Pool Mapping         │ │
          │  │  - "project-a" → Pool (4 workers)  │ │
          │  │  - "project-b" → Pool (2 workers)  │ │
          │  └────────────────────────────────────┘ │
          └──────────────────┬──────────────────────┘
                             │
          ┌──────────────────▼──────────────────────┐
          │     BigQueryProcessPool (per project)    │
          │                                          │
          │  Main Process:                           │
          │  ┌────────────┐  ┌──────────────┐       │
          │  │ Task Queue │  │ Result Queue │       │
          │  └─────┬──────┘  └──────▲───────┘       │
          │        │                 │               │
          │        │   ┌─────────────┴──────┐       │
          │        │   │ Result Dispatcher  │       │
          │        │   │    (Thread)        │       │
          │        │   └────────────────────┘       │
          │        │                                 │
          │  ┌─────▼───────┐  ┌──────────────┐     │
          │  │  Worker 1   │  │  Worker N    │     │
          │  │  (Process)  │  │  (Process)   │     │
          │  │             │  │              │     │
          │  │ BQ Client   │  │  BQ Client   │     │
          │  └─────────────┘  └──────────────┘     │
          └──────────────────────────────────────────┘
                             │
          ┌──────────────────▼──────────────────────┐
          │         Google BigQuery Service          │
          └──────────────────────────────────────────┘
```

### Key Components

1. **BigQueryPoolManager**: Singleton that manages shared pools across the application
2. **BigQueryProcessPool**: Manages worker processes for a specific GCP project
3. **Worker Processes**: Independent processes that execute BigQuery queries
4. **Result Dispatcher**: Background thread that routes results to async futures
5. **BigQueryIndexBase**: High-level interface for table operations

## Usage Patterns

### 1. Using Shared Pools (Recommended)

Shared pools allow multiple table indices to use the same worker pool, improving resource efficiency:

```python
from bq import BigQueryIndexBase

# All indices automatically use shared pool by default
users_index = BigQueryIndexBase(
    proj_dataset_id="my-project.my_dataset",
    schema_path="schemas/table_schema.json",
    schema_key="users",
    use_shared_pool=True  # Default
)
users_index.set_current_table("users")

messages_index = BigQueryIndexBase(
    proj_dataset_id="my-project.my_dataset",
    schema_path="schemas/table_schema.json",
    schema_key="messages",
    use_shared_pool=True  # Shares pool with users_index
)
messages_index.set_current_table("messages")

# Start pool once (all indices share it)
users_index.start_pool()

# Execute queries from any index
results = await users_index.run_queries(
    "SELECT * FROM {dataset_table_id} WHERE email = @email",
    records=[{"email": "user@example.com"}]
)

# Access results (always list of lists)
if results and results[0]:
    user_row = results[0][0]
    print(user_row['id'])
```

### 2. Using Dedicated Pools

For isolated workloads or different projects:

```python
from bq import BigQueryIndexBase

index = BigQueryIndexBase(
    proj_dataset_id="my-project.my_dataset",
    schema_path="schemas/table_schema.json",
    schema_key="large_table",
    use_shared_pool=False,  # Create dedicated pool
    pool_num_workers=8,      # Custom worker count
    pool_query_timeout_secs=60
)
index.set_current_table("large_table")
index.start_pool()

# This index has its own 8-worker pool
results = await index.run_queries("SELECT COUNT(*) as cnt FROM {dataset_table_id}")
count = results[0][0]['cnt']

# Stop dedicated pool when done
index.stop_pool()
```

### 3. Direct Pool Access

For fine-grained control:

```python
from bq.pool_manager import get_shared_pool

# Get or create shared pool
pool = get_shared_pool(
    proj_id="my-project",
    num_workers=4,
    query_timeout=30,
    auto_start=True
)

# Execute queries directly
results = await pool.run_query(
    queries=["SELECT * FROM `my-project.dataset.table` LIMIT 10"],
    timeout=60
)

# Results are list of lists
rows = results[0]
for row in rows:
    print(row)
```

## Query Execution Modes

### Sequential Queries (Single Batch)

Submit all queries as a single task to one worker:

```python
queries = [
    "SELECT COUNT(*) FROM table1",
    "SELECT COUNT(*) FROM table2",
    "SELECT COUNT(*) FROM table3"
]

# distribute=False: All queries sent to one worker
results = await pool.run_query(queries, distribute=False)

# Results structure: [[result_q1, result_q2, result_q3]]
# All results are in results[0]
for idx, query_results in enumerate(results[0]):
    print(f"Query {idx}: {query_results}")
```

### Distributed Queries (Parallel)

Distribute queries across available workers for parallel execution:

```python
queries = [
    "SELECT COUNT(*) FROM table1",
    "SELECT COUNT(*) FROM table2",
    "SELECT COUNT(*) FROM table3"
]

# distribute=True: Each query sent to different worker
results = await pool.run_query(queries, distribute=True)

# Results structure: [[result_q1], [result_q2], [result_q3]]
# Each query result is in its own list
count1 = results[0][0]['f0_']  # First query result
count2 = results[1][0]['f0_']  # Second query result
count3 = results[2][0]['f0_']  # Third query result
```

### Parameterized Queries

Execute the same query with different parameters:

```python
from google.cloud import bigquery

# Build job configs with parameters
job_configs = [
    bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "STRING", "user-123")
        ]
    ),
    bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "STRING", "user-456")
        ]
    )
]

# Execute in parallel
results = await pool.run_query(
    queries=[
        "SELECT * FROM `project.dataset.table` WHERE user_id = @user_id",
        "SELECT * FROM `project.dataset.table` WHERE user_id = @user_id"
    ],
    job_configs=job_configs,
    distribute=True
)

# Each parameter set has its own result
user_123_data = results[0]  # Results for user-123
user_456_data = results[1]  # Results for user-456
```

## Result Structure

**Critical**: All query methods return a **list of lists** structure:

```python
results = await index.run_queries(query, records=[{"id": "123"}])

# Structure: [[row1, row2, ...]]
# Outer list: One element per query execution
# Inner lists: Rows returned by each query
# Each row: Dictionary with column names as keys

# ✅ CORRECT: Access first query's results
if results and results[0]:
    for row in results[0]:
        print(row['column_name'])
    
    # Or access first row directly
    first_row = results[0][0]
    value = first_row['column_name']

# ❌ INCORRECT: This will cause "list indices must be integers" error
for row in results:  # 'row' is a LIST, not a dict!
    print(row['column_name'])  # ERROR!
```

### Multiple Queries Results

```python
# Multiple parameterized queries
results = await index.run_queries(
    "SELECT * FROM {dataset_table_id} WHERE id = @id",
    records=[
        {"id": "123"},
        {"id": "456"},
        {"id": "789"}
    ]
)

# Structure: [[rows_for_123], [rows_for_456], [rows_for_789]]
rows_123 = results[0]  # All rows where id='123'
rows_456 = results[1]  # All rows where id='456'
rows_789 = results[2]  # All rows where id='789'

# Access specific row from specific query
if results[0]:  # Check if first query returned results
    first_row = results[0][0]
    print(first_row['column_name'])
```

## Common Patterns

### Pattern 1: Get Single Record

```python
async def get_user_by_email(email: str) -> Optional[str]:
    results = await users_index.run_queries(
        "SELECT * FROM {dataset_table_id} WHERE email = @email",
        records=[{"email": email}]
    )
    
    # Check if results exist and have rows
    if results and results[0]:
        return results[0][0]['id']  # First row of first query
    return None
```

### Pattern 2: Get Multiple Records

```python
async def get_messages(conversation_id: str) -> List[Dict]:
    results = await messages_index.run_queries(
        "SELECT * FROM {dataset_table_id} WHERE conversation_id = @conversation_id ORDER BY `order` ASC",
        records=[{"conversation_id": conversation_id}]
    )
    
    messages = []
    if results and results[0]:
        for row in results[0]:  # Iterate over rows in first query
            messages.append({
                "id": row['id'],
                "content": row['content'],
                "role": row['role']
            })
    return messages
```

### Pattern 3: Aggregate Query

```python
async def get_max_order(conversation_id: str) -> int:
    results = await messages_index.run_queries(
        "SELECT MAX(`order`) as max_order FROM {dataset_table_id} WHERE conversation_id = @conversation_id",
        records=[{"conversation_id": conversation_id}]
    )
    
    if results and results[0] and results[0][0]['max_order'] is not None:
        return results[0][0]['max_order']
    return -1
```

### Pattern 4: Existence Check

```python
async def record_exists(record_id: str) -> bool:
    results = await index.run_queries(
        "SELECT COUNT(*) as cnt FROM {dataset_table_id} WHERE id = @id",
        records=[{"id": record_id}]
    )
    
    if results and results[0]:
        return results[0][0]['cnt'] > 0
    return False
```

### Pattern 5: Batch Query with Different Parameters

```python
async def get_multiple_users(user_ids: List[str]) -> List[Dict]:
    results = await users_index.run_queries(
        "SELECT * FROM {dataset_table_id} WHERE id = @id",
        records=[{"id": uid} for uid in user_ids]
    )
    
    # results[i] contains rows for user_ids[i]
    users = []
    for query_result in results:
        if query_result:  # Check if this query returned rows
            users.extend(query_result)  # Add all rows from this query
    return users
```

## Pool Management

### Starting Pools

```python
# Shared pool (recommended)
index.start_pool()  # Start once, shared across all indices

# Check if started
status = index.client_pool.get_pool_status()
print(f"Workers ready: {status['workers_ready']}/{status['workers_total']}")
```

### Monitoring Pool Health

```python
from bq.pool_manager import get_pool_manager_status

# Get status of all pools
status = get_pool_manager_status()
for project_id, pool_status in status.items():
    print(f"Project: {project_id}")
    print(f"  Running: {pool_status['running']}")
    print(f"  Workers: {pool_status['workers_alive']}/{pool_status['workers_total']}")
    print(f"  Pending: {pool_status['pending_tasks']}")
    print(f"  Processed: {pool_status['tasks_processed']}")
```

### Stopping Pools

```python
# Stop dedicated pool
index.stop_pool()

# Stop specific shared pool
from bq.pool_manager import BigQueryPoolManager
manager = BigQueryPoolManager()
manager.stop_pool("my-project")

# Stop all shared pools (e.g., at application shutdown)
from bq.pool_manager import stop_all_shared_pools
stop_all_shared_pools()
```

### Application Shutdown

```python
import atexit
from bq.pool_manager import stop_all_shared_pools

# Register cleanup handler
atexit.register(stop_all_shared_pools)

# Or in async context
async def shutdown():
    stop_all_shared_pools()
    # Wait for cleanup
    await asyncio.sleep(1)
```

## Performance Tuning

### Worker Count

```python
# For I/O bound workloads (typical): 2-4 workers per project
pool = get_shared_pool(proj_id="my-project", num_workers=4)

# For high throughput: 8-16 workers
pool = get_shared_pool(proj_id="my-project", num_workers=16)

# Consider: More workers = more processes = more memory
# But: More workers = better parallelism for distributed queries
```

### Query Timeout

```python
# Default timeout (applied to all queries)
pool = BigQueryProcessPool(proj_id="my-project", query_timeout=30)

# Per-query timeout override
results = await pool.run_query(queries, timeout=120)  # 120 seconds
```

### Distributed vs Batch

```python
# Use distribute=True when:
# - Queries are independent
# - Queries have similar execution time
# - You have available workers
results = await pool.run_query(queries, distribute=True)

# Use distribute=False when:
# - Queries are sequential/dependent
# - You have many small queries
# - Worker count is limited
results = await pool.run_query(queries, distribute=False)
```

## Error Handling

### Pool Not Started

```python
try:
    results = await index.run_queries(query)
except RuntimeError as e:
    if "Pool not started" in str(e):
        index.start_pool()
        results = await index.run_queries(query)
```

### Worker Health Issues

```python
try:
    results = await pool.run_query(queries)
except RuntimeError as e:
    if "unhealthy" in str(e):
        # Check status
        status = pool.get_pool_status()
        print(f"Workers alive: {status['workers_alive']}")
        
        # Restart pool
        pool.stop()
        pool.start()
```

### Query Timeout

```python
import asyncio

try:
    results = await pool.run_query(queries, timeout=30)
except asyncio.TimeoutError:
    print("Query timed out after 30 seconds")
    # Handle timeout (retry, log, etc.)
```

## Best Practices

1. **Use Shared Pools**: Always prefer `use_shared_pool=True` unless you have specific isolation requirements

2. **Start Pool Once**: Start the pool at application startup, not per-request

3. **Access Results Correctly**: Always use `results[query_index][row_index]` pattern

4. **Check for Empty Results**: Always check `if results and results[0]` before accessing

5. **Cleanup on Exit**: Register `stop_all_shared_pools()` with `atexit`

6. **Monitor Health**: Periodically check pool status in production

7. **Tune Worker Count**: Start with 2-4 workers, increase based on load

8. **Use Distribute Wisely**: Enable for independent queries, disable for sequential

9. **Handle Errors**: Wrap pool operations in try-except blocks

10. **Parameter Validation**: Ensure parameter keys match schema definitions

## Troubleshooting

### "list indices must be integers or slices" Error

**Cause**: Iterating over results directly instead of accessing nested structure

```python
# ❌ Wrong
for row in results:
    print(row['column'])

# ✅ Correct
for row in results[0]:
    print(row['column'])
```

### "Pool not started" Error

**Cause**: Calling run_queries before starting pool

```python
# ✅ Solution
index.start_pool()
results = await index.run_queries(query)
```

### "Worker pool unhealthy" Error

**Cause**: Worker processes died or failed to initialize

```python
# ✅ Solution
status = pool.get_pool_status()
if status['workers_alive'] < status['workers_total']:
    pool.stop()
    pool.start()
```

### Workers Stuck or Not Processing

**Cause**: Queue deadlock or worker process crash

```python
# ✅ Solution: Restart pool
pool.stop()
time.sleep(1)
pool.start()
```

## Examples

See the following files for complete examples:
- `src/services/users.py` - Real-world usage in user service
- `src/common.py` - Simple query execution
- `test_shared_pool.py` - Pool testing and benchmarking

## API Reference

### BigQueryProcessPool

- `__init__(proj_id, num_workers, query_timeout)` - Initialize pool
- `start()` - Start worker processes
- `stop()` - Stop pool and cleanup
- `run_query(queries, job_configs, timeout, distribute)` - Execute queries
- `get_pool_status()` - Get pool health metrics

### BigQueryIndexBase

- `__init__(proj_dataset_id, schema_path, schema_key, use_shared_pool)` - Initialize index
- `set_current_table(table_name)` - Set active table
- `start_pool()` - Start the pool (shared or dedicated)
- `stop_pool()` - Stop pool if owned
- `run_queries(base_query, records)` - Execute parameterized queries
- `insert_records(records)` - Insert records into table
- `update_records(base_query, records)` - Update records
- `delete_records(base_query, records)` - Delete records

### BigQueryPoolManager

- `get_pool(proj_id, num_workers, query_timeout, auto_start)` - Get/create pool
- `stop_pool(proj_id)` - Stop specific pool
- `stop_all_pools()` - Stop all pools
- `get_status()` - Get all pool statuses

## Environment Variables

```bash
# Pool configuration
export BQ_POOL_NUM_WORKERS=4
export BQ_POOL_QUERY_TIMEOUT=30

# BigQuery configuration
export GOOGLE_CREDENTIALS="<base64-encoded-credentials>"
export BQ_PROJECT_DATASET_ID="my-project.my_dataset"
export BQ_SCHEMA_PATH="schemas/table_schema.json"
export BQ_SCHEMA_KEY="my_table"
```

