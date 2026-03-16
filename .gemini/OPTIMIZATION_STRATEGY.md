# Optimization Strategy: Hybrid Streaming + In-Memory Architecture

## Core Philosophy

**Key Insight**: Not all operations can be streamed. We need a **hybrid approach**:
- **Stream simple operations** (filters, projections, simple transforms)
- **Use temporary tables for complex operations** (aggregations, joins, window functions)
- **Chunk large datasets** to keep memory usage bounded

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    OPTIMIZATION STRATEGY                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Source DB ──┐                                                  │
│              │                                                   │
│              ├──► Streaming Extract (chunks of 10K rows)        │
│              │                                                   │
│              └──► Decision Point:                               │
│                   │                                              │
│                   ├─ Simple Transform? ──► Stream Processing    │
│                   │   (filter, projection)   (low memory)       │
│                   │                                              │
│                   └─ Complex Transform? ──► Temp Table Strategy │
│                       (join, aggregate,      (bounded memory)   │
│                        window function)                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         TEMP TABLE STRATEGY (for aggregations)           │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  1. Stream chunks to temp table in destination DB        │  │
│  │  2. Run SQL aggregation on temp table                    │  │
│  │  3. Stream results to final destination                  │  │
│  │  4. Drop temp table                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Strategy by Operation Type

### 1. **Simple Transforms** (Filter, Projection, Compute)
**Strategy**: Streaming with bounded memory

```python
# Current (loads all data):
data = await extract_all()  # 1M rows in memory
filtered = [row for row in data if row['age'] > 18]  # Still 1M rows processed

# Optimized (streaming):
async for chunk in extract_chunks(chunk_size=10000):
    filtered_chunk = [row for row in chunk if row['age'] > 18]
    await load_chunk(filtered_chunk)
# Memory: Only 10K rows at a time
```

**Memory**: O(chunk_size) = ~10K rows = ~10-50 MB
**Speedup**: 10-100x for large datasets

---

### 2. **Aggregations** (GROUP BY, SUM, COUNT, AVG)
**Problem**: Cannot stream - need all data to compute aggregates

**Strategy**: Temporary table in destination DB

```python
# Option A: Temp Table Strategy (RECOMMENDED)
async def execute_aggregation_node(node, upstream_data):
    # 1. Stream upstream data to temp table
    temp_table = f"temp_agg_{node_id}_{uuid4()}"
    await stream_to_temp_table(upstream_data, temp_table)
    
    # 2. Run aggregation in database (FAST!)
    agg_sql = f"""
        SELECT 
            department,
            COUNT(*) as employee_count,
            AVG(salary) as avg_salary
        FROM {temp_table}
        GROUP BY department
    """
    result = await execute_sql(agg_sql)
    
    # 3. Drop temp table
    await drop_table(temp_table)
    
    return result

# Memory: Only aggregated results (small)
# Speed: Database does aggregation (optimized, indexed)
```

**Memory**: O(num_groups) instead of O(num_rows)
**Example**: 1M rows → 50 departments = 50 rows in memory

---

### 3. **Joins** (INNER, LEFT, RIGHT, FULL)
**Problem**: Need both datasets to join

**Strategy**: Hybrid - temp tables for large joins, in-memory for small

```python
async def execute_join_node(node, left_data, right_data):
    left_size = estimate_size(left_data)
    right_size = estimate_size(right_data)
    
    # Small join (< 100K rows total): In-memory
    if left_size + right_size < 100_000:
        return join_in_memory(left_data, right_data, conditions)
    
    # Large join: Temp table strategy
    else:
        # 1. Stream both sides to temp tables
        left_temp = f"temp_join_left_{uuid4()}"
        right_temp = f"temp_join_right_{uuid4()}"
        
        await stream_to_temp_table(left_data, left_temp)
        await stream_to_temp_table(right_data, right_temp)
        
        # 2. SQL join (database optimized)
        join_sql = f"""
            SELECT l.*, r.*
            FROM {left_temp} l
            INNER JOIN {right_temp} r
            ON l.customer_id = r.customer_id
        """
        result = await execute_sql_streaming(join_sql)
        
        # 3. Cleanup
        await drop_table(left_temp)
        await drop_table(right_temp)
        
        return result

# Memory: Bounded by chunk size during streaming
```

**Memory**: O(chunk_size) during load, O(result_size) for output
**Speedup**: Database join algorithms are highly optimized

---

### 4. **Window Functions** (ROW_NUMBER, RANK, LAG, LEAD)
**Problem**: Need entire partition in memory

**Strategy**: Temp table with SQL window functions

```python
async def execute_window_node(node, upstream_data):
    temp_table = f"temp_window_{uuid4()}"
    await stream_to_temp_table(upstream_data, temp_table)
    
    # Database handles window function
    window_sql = f"""
        SELECT 
            *,
            ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) as rank
        FROM {temp_table}
    """
    result = await execute_sql_streaming(window_sql)
    
    await drop_table(temp_table)
    return result

# Memory: Streaming results back
```

---

## Implementation Plan

### Phase 1: Add Streaming Infrastructure (Week 1)

#### 1.1 Modify Extraction Service to Support Chunking

```python
# services/extraction_service/main.py

@app.post("/extract/stream")
async def extract_stream(request: ExtractionRequest):
    """
    Stream extraction in chunks. Returns job_id.
    Client polls /extract/{job_id}/chunk/{chunk_num} for each chunk.
    """
    job_id = str(uuid4())
    
    # Start background extraction
    background_tasks.add_task(
        extract_and_chunk,
        job_id,
        request.table_name,
        request.connection_config,
        chunk_size=request.chunk_size or 10000
    )
    
    return {"job_id": job_id, "status": "streaming"}


async def extract_and_chunk(job_id, table_name, connection_config, chunk_size):
    """Extract data in chunks and store each chunk separately."""
    offset = 0
    chunk_num = 0
    
    while True:
        # Fetch chunk
        chunk = await fetch_chunk(table_name, connection_config, offset, chunk_size)
        
        if not chunk:
            break
        
        # Store chunk (in-memory or Redis)
        extraction_jobs[job_id][f"chunk_{chunk_num}"] = chunk
        extraction_jobs[job_id]["total_chunks"] = chunk_num + 1
        
        offset += chunk_size
        chunk_num += 1
    
    extraction_jobs[job_id]["status"] = "completed"


@app.get("/extract/{job_id}/chunk/{chunk_num}")
async def get_chunk(job_id: str, chunk_num: int):
    """Get specific chunk of extracted data."""
    if job_id not in extraction_jobs:
        raise HTTPException(404, "Job not found")
    
    chunk_key = f"chunk_{chunk_num}"
    if chunk_key not in extraction_jobs[job_id]:
        raise HTTPException(404, "Chunk not found")
    
    return {
        "chunk_num": chunk_num,
        "data": extraction_jobs[job_id][chunk_key],
        "total_chunks": extraction_jobs[job_id].get("total_chunks")
    }
```

#### 1.2 Add Streaming Orchestrator Methods

```python
# services/migration_service/orchestrator.py

async def _execute_source_node_streaming(self, node, config):
    """Execute source node with streaming extraction."""
    # Start streaming extraction
    response = await self.client.post(
        f"{self.extraction_service_url}/extract/stream",
        json=extraction_request
    )
    job_id = response.json()["job_id"]
    
    # Return generator instead of full data
    return {
        "success": True,
        "node_id": node.get("id"),
        "data_stream": self._stream_chunks(job_id),
        "is_streaming": True
    }


async def _stream_chunks(self, job_id):
    """Generator that yields chunks as they become available."""
    chunk_num = 0
    
    while True:
        try:
            response = await self.client.get(
                f"{self.extraction_service_url}/extract/{job_id}/chunk/{chunk_num}"
            )
            chunk_data = response.json()
            
            yield chunk_data["data"]
            
            # Check if this was the last chunk
            if chunk_num + 1 >= chunk_data.get("total_chunks", float('inf')):
                break
            
            chunk_num += 1
            
        except HTTPException as e:
            if e.status_code == 404:
                # Chunk not ready yet, wait
                await asyncio.sleep(0.5)
            else:
                raise
```

---

### Phase 2: Implement Temp Table Strategy (Week 2)

#### 2.1 Add Temp Table Utilities

```python
# services/migration_service/temp_table_manager.py

class TempTableManager:
    """Manages temporary tables in destination database for complex operations."""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.temp_tables = []
    
    async def create_temp_table_from_stream(
        self, 
        data_stream: AsyncGenerator,
        table_name: str,
        schema: Optional[List[Dict]] = None
    ) -> str:
        """
        Stream data into a temporary table.
        Returns the temp table name.
        """
        # Create temp table
        if schema:
            columns = [(col["name"], col["datatype"]) for col in schema]
        else:
            # Infer from first chunk
            first_chunk = await anext(data_stream)
            columns = self._infer_columns(first_chunk)
            # Put first chunk back
            data_stream = self._prepend_chunk(first_chunk, data_stream)
        
        create_sql = self._build_create_temp_table_sql(table_name, columns)
        await self.db.execute(create_sql)
        self.temp_tables.append(table_name)
        
        # Stream data into temp table
        async for chunk in data_stream:
            await self._insert_chunk(table_name, chunk)
        
        return table_name
    
    async def execute_sql_on_temp(self, sql: str) -> AsyncGenerator:
        """
        Execute SQL on temp tables and stream results.
        Useful for aggregations, joins, window functions.
        """
        cursor = await self.db.execute(sql)
        
        # Stream results in chunks
        while True:
            rows = await cursor.fetchmany(10000)
            if not rows:
                break
            yield rows
    
    async def cleanup(self):
        """Drop all temp tables created by this manager."""
        for table in self.temp_tables:
            try:
                await self.db.execute(f"DROP TABLE IF EXISTS {table}")
            except Exception as e:
                logger.warning(f"Failed to drop temp table {table}: {e}")
        
        self.temp_tables.clear()
```

#### 2.2 Modify Transform Nodes to Use Temp Tables

```python
# services/migration_service/orchestrator.py

async def _execute_transform_node(self, node, previous_results, config):
    """Execute transform with automatic strategy selection."""
    node_type = node.get("type").lower()
    node_config = node.get("data", {}).get("config", {})
    
    # Get upstream data (may be streaming or in-memory)
    upstream = self._get_upstream_result(node, previous_results)
    
    # Strategy selection based on node type and data size
    if node_type == "filter" or node_type == "projection":
        # Simple transforms: streaming
        return await self._execute_streaming_transform(node, upstream)
    
    elif node_type == "aggregate":
        # Aggregation: temp table strategy
        return await self._execute_aggregation_temp_table(node, upstream, config)
    
    elif node_type == "join":
        # Join: hybrid strategy
        left, right = self._get_join_inputs(node, previous_results)
        return await self._execute_join_hybrid(node, left, right, config)
    
    elif node_type == "window":
        # Window function: temp table strategy
        return await self._execute_window_temp_table(node, upstream, config)
    
    else:
        # Fallback: in-memory
        return await self._execute_in_memory_transform(node, upstream)


async def _execute_aggregation_temp_table(self, node, upstream, config):
    """Execute aggregation using temp table strategy."""
    node_id = node.get("id")
    agg_config = node.get("data", {}).get("config", {})
    
    # Get destination connection for temp table
    dest_config = self._get_destination_config(config)
    temp_mgr = TempTableManager(dest_config)
    
    try:
        # 1. Stream upstream data to temp table
        temp_table = f"temp_agg_{node_id}_{uuid4().hex[:8]}"
        
        if upstream.get("is_streaming"):
            await temp_mgr.create_temp_table_from_stream(
                upstream["data_stream"],
                temp_table
            )
        else:
            # Convert in-memory data to stream
            async def data_gen():
                yield upstream["data"]
            await temp_mgr.create_temp_table_from_stream(
                data_gen(),
                temp_table
            )
        
        # 2. Build aggregation SQL
        group_by = agg_config.get("groupBy", [])
        aggregates = agg_config.get("aggregates", [])
        
        agg_sql = self._build_aggregation_sql(temp_table, group_by, aggregates)
        
        # 3. Execute aggregation in database
        result_chunks = []
        async for chunk in temp_mgr.execute_sql_on_temp(agg_sql):
            result_chunks.extend(chunk)
        
        return {
            "success": True,
            "node_id": node_id,
            "data": result_chunks,
            "is_streaming": False,
            "stats": {"rows_aggregated": len(result_chunks)}
        }
    
    finally:
        # 4. Cleanup temp table
        await temp_mgr.cleanup()


def _build_aggregation_sql(self, table: str, group_by: List[str], aggregates: List[Dict]) -> str:
    """Build SQL for aggregation."""
    # SELECT clause
    select_parts = []
    for col in group_by:
        select_parts.append(f'"{col}"')
    
    for agg in aggregates:
        func = agg["function"].upper()  # SUM, COUNT, AVG, MIN, MAX
        col = agg["column"]
        alias = agg.get("alias", f"{func}_{col}")
        select_parts.append(f'{func}("{col}") AS "{alias}"')
    
    select_clause = ", ".join(select_parts)
    
    # GROUP BY clause
    if group_by:
        group_clause = "GROUP BY " + ", ".join(f'"{col}"' for col in group_by)
    else:
        group_clause = ""
    
    return f'SELECT {select_clause} FROM "{table}" {group_clause}'
```

---

### Phase 3: Intelligent Strategy Selection (Week 3)

#### 3.1 Add Size Estimation

```python
# services/migration_service/strategy_selector.py

class TransformStrategy(Enum):
    STREAMING = "streaming"          # For simple transforms
    IN_MEMORY = "in_memory"          # For small datasets
    TEMP_TABLE = "temp_table"        # For complex operations
    HYBRID = "hybrid"                # For joins


class StrategySelector:
    """Selects optimal execution strategy based on data characteristics."""
    
    # Thresholds (configurable)
    SMALL_DATASET_THRESHOLD = 50_000      # rows
    MEMORY_LIMIT_MB = 500                  # MB
    
    @staticmethod
    def estimate_row_count(upstream_result: Dict) -> int:
        """Estimate number of rows from upstream result."""
        if "row_count" in upstream_result:
            return upstream_result["row_count"]
        
        if "data" in upstream_result and isinstance(upstream_result["data"], list):
            return len(upstream_result["data"])
        
        # Default: assume large
        return 1_000_000
    
    @staticmethod
    def estimate_memory_mb(row_count: int, num_columns: int = 20) -> float:
        """Estimate memory usage in MB."""
        # Rough estimate: 500 bytes per row (dict overhead + data)
        bytes_per_row = 500 + (num_columns * 50)
        total_bytes = row_count * bytes_per_row
        return total_bytes / (1024 * 1024)
    
    @classmethod
    def select_strategy(
        cls,
        node_type: str,
        upstream_results: List[Dict],
        config: Dict
    ) -> TransformStrategy:
        """Select optimal strategy for this transform."""
        
        # Simple transforms: always stream if possible
        if node_type in ("filter", "projection", "compute"):
            return TransformStrategy.STREAMING
        
        # Estimate data size
        total_rows = sum(cls.estimate_row_count(r) for r in upstream_results)
        estimated_memory = cls.estimate_memory_mb(total_rows)
        
        # Complex transforms
        if node_type == "aggregate":
            if total_rows < cls.SMALL_DATASET_THRESHOLD:
                return TransformStrategy.IN_MEMORY
            else:
                return TransformStrategy.TEMP_TABLE
        
        elif node_type == "join":
            if total_rows < cls.SMALL_DATASET_THRESHOLD:
                return TransformStrategy.IN_MEMORY
            else:
                return TransformStrategy.TEMP_TABLE
        
        elif node_type == "window":
            # Window functions almost always need temp table
            return TransformStrategy.TEMP_TABLE
        
        # Default: in-memory for backward compatibility
        return TransformStrategy.IN_MEMORY
```

---

## Memory Usage Comparison

### Current Architecture:
```
Operation: Extract 1M rows → Filter → Aggregate → Load

Memory Timeline:
Extract:    [████████████████████] 4 GB (all rows)
Filter:     [████████████████████] 4 GB (all rows)
Aggregate:  [████████████████████] 4 GB (all rows)
Load:       [████████████████████] 4 GB (all rows)

Peak Memory: 4 GB
Duration: 120 seconds
```

### Optimized Architecture:
```
Operation: Extract 1M rows → Filter → Aggregate → Load

Memory Timeline:
Extract:    [█] 10 MB (chunk of 10K)
Filter:     [█] 10 MB (chunk of 10K)
Aggregate:  [█] 50 MB (temp table + results)
Load:       [█] 10 MB (chunk of 10K)

Peak Memory: 50 MB
Duration: 40 seconds
```

**Improvement**: 80x less memory, 3x faster

---

## Configuration

Add to `config` dict:

```python
config = {
    "optimization": {
        "enable_streaming": True,
        "chunk_size": 10000,
        "memory_limit_mb": 500,
        "use_temp_tables": True,
        "temp_table_db": "destination",  # or "dedicated"
        "strategy": "auto"  # or "streaming", "temp_table", "in_memory"
    }
}
```

---

## Rollout Plan

### Week 1: Streaming Infrastructure
- [ ] Add chunked extraction endpoint
- [ ] Modify orchestrator to handle streaming
- [ ] Test with simple filter/projection nodes

### Week 2: Temp Table Strategy
- [ ] Implement TempTableManager
- [ ] Add aggregation via temp tables
- [ ] Add join via temp tables
- [ ] Test with complex pipelines

### Week 3: Strategy Selection
- [ ] Implement StrategySelector
- [ ] Add automatic strategy selection
- [ ] Add monitoring/metrics
- [ ] Performance testing

### Week 4: Production Rollout
- [ ] Feature flag for gradual rollout
- [ ] Monitor memory usage
- [ ] Optimize based on real workloads
- [ ] Documentation

---

## Monitoring

Add metrics to track:

```python
# In orchestrator
metrics = {
    "node_id": node_id,
    "strategy_used": "temp_table",
    "rows_processed": 1_000_000,
    "memory_peak_mb": 45,
    "duration_seconds": 38,
    "temp_tables_created": 2,
    "chunks_processed": 100
}
```

---

## Fallback Strategy

If temp table strategy fails:
1. Log warning
2. Fall back to in-memory processing
3. Alert if memory threshold exceeded
4. Suggest increasing resources or chunking

```python
try:
    result = await execute_with_temp_table(node, data)
except Exception as e:
    logger.warning(f"Temp table strategy failed: {e}, falling back to in-memory")
    result = await execute_in_memory(node, data)
```

---

## Summary

**For Aggregations and Complex Operations:**

1. **Use Temporary Tables in Destination DB**
   - Stream data to temp table
   - Let database do the heavy lifting
   - Stream results back
   - Memory stays bounded

2. **Automatic Strategy Selection**
   - Small data (< 50K rows): In-memory (fast)
   - Large data: Temp table (memory-efficient)
   - Simple transforms: Streaming (fastest)

3. **Benefits**:
   - ✅ Memory usage: O(chunk_size) instead of O(total_rows)
   - ✅ Speed: Database-optimized aggregations/joins
   - ✅ Scalability: Handle datasets of any size
   - ✅ Reliability: No OOM errors

**The key insight**: You don't need to keep everything in memory. Use the destination database as a temporary workspace for complex operations!
