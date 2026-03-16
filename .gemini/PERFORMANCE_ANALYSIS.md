# Performance Analysis: Execute Button Slowness

## Executive Summary

The system slowness when triggering the execute button is caused by **in-memory data processing** throughout the entire pipeline. The system loads ALL data into memory, transforms it in memory, and only writes to the database at the final destination step. This creates significant memory pressure and performance bottlenecks for large datasets.

---

## Key Findings

### 1. **Data Flow Architecture**

The current architecture follows this pattern:

```
Source DB → Extraction Service (fetch ALL rows) → In-Memory Storage → 
Transform in Memory → Destination Loader → Bulk Insert to DB
```

**Critical Issue**: The entire dataset is held in memory as Python dictionaries throughout the pipeline.

### 2. **Where Data is Stored During Execution**

#### **Extraction Phase** (`services/extraction_service/main.py`)
- Extraction service fetches ALL rows from source database
- Stores complete dataset in memory as `List[Dict[str, Any]]`
- Returns via HTTP to orchestrator
- **No streaming, no chunking, no pagination**

#### **Orchestration Phase** (`services/migration_service/orchestrator.py`)
- Line 246: `results = {}` - stores ALL node outputs in memory
- Line 454: `data = await self._wait_for_extraction(job_id)` - fetches entire dataset
- Line 456-460: Returns full dataset as `{"data": data}` where data is list of dicts
- Line 713-731: `_get_input_data()` passes entire dataset between nodes

#### **Transform Phase** (In-Memory Operations)
- **Join Node** (Line 24-119): `_join_in_memory()` - performs joins on full datasets in memory
- **Filter/Projection** (Line 515-523): Pass-through entire dataset
- All transformations work on complete `List[Dict[str, Any]]`

#### **Destination Phase** (`services/migration_service/postgres_loader.py`)
- Line 273-427: `load_data()` receives entire dataset
- Line 385: Converts all rows to list format for bulk insert
- Line 391: Uses PostgreSQL COPY for bulk load (good for performance)
- Line 404: Fallback to `executemany` in batches of 500

---

## 3. **WebSocket Data Logging**

### What You're Seeing in WebSocket Logs

The "data in form of dictionary" you're seeing in WebSocket logs is **NOT the actual row data**. It's progress/status messages:

**Location**: `services/websocket_server/main.py`
- Line 128: `logger.info(f"[WEBSOCKET] Broadcast data: {json.dumps(data, indent=2)}")`

**What's being logged**:
```python
{
    "type": "status",
    "status": "running", 
    "progress": 45.0,
    "current_step": "Level 2/3: running 1 node(s) in parallel",
    "current_level": 2,
    "total_levels": 3,
    "level_status": "running"
}
```

**NOT row data**, just metadata about job progress.

---

## 4. **Database Insert Mechanism**

### PostgreSQL Loader (`postgres_loader.py`)

**Good News**: The loader uses efficient bulk insert methods:

1. **Primary Method**: PostgreSQL COPY (Line 122-138)
   - Fastest bulk load method
   - Converts rows to CSV format in memory
   - Uses `cursor.copy_expert()` for direct COPY FROM STDIN
   - **This is NOT the bottleneck**

2. **Fallback Method**: `executemany` (Line 404)
   - Batches of 500 rows
   - Only used if COPY fails
   - Still reasonably efficient

### Data Format to Database

**Question**: "Is data passed to DB in form of dictionary?"

**Answer**: 
- **Input to loader**: Yes, `List[Dict[str, Any]]` (line 275)
- **Conversion**: Dictionaries are converted to row tuples (line 385)
- **Insert**: Rows are inserted as VALUES, not as JSON/dictionaries
- **Table structure**: Normal relational columns, NOT JSONB

```python
# Line 385: Conversion from dict to row tuple
rows = [[row.get(norm_to_orig.get(col, col)) for col in columns] for row in data]
```

---

## 5. **Performance Bottlenecks Identified**

### Primary Bottlenecks (Ranked by Impact):

#### **1. Full Dataset in Memory** ⭐⭐⭐⭐⭐ (CRITICAL)
- **Location**: Throughout entire pipeline
- **Impact**: 
  - Large datasets (>100K rows) cause memory exhaustion
  - Python dict overhead: ~280 bytes per dict + key/value storage
  - For 1M rows × 20 columns: ~5-10 GB memory
- **Symptoms**: 
  - System slowdown
  - Possible swapping to disk
  - OOM errors on large datasets

#### **2. No Streaming/Chunking** ⭐⭐⭐⭐
- **Location**: Extraction service → Orchestrator
- **Impact**:
  - Must wait for ALL rows before processing starts
  - Cannot start transformations until extraction completes
  - Network transfer of large JSON payloads
- **Current**: `await self._wait_for_extraction(job_id)` waits for complete dataset

#### **3. Synchronous Level Execution** ⭐⭐⭐
- **Location**: `orchestrator.py` line 259-326
- **Impact**:
  - Levels execute sequentially (correct for dependencies)
  - But within a level, nodes run in parallel (good)
  - Still, data must be fully in memory for each level

#### **4. Multiple Data Copies** ⭐⭐
- **Location**: Various points
- **Impact**:
  - Extraction service stores data
  - Orchestrator stores in `results` dict
  - Each transform node may create copies
  - Destination loader receives copy
  - Remap operations create new dicts (line 555-560)

---

## 6. **Why It's Slow: Detailed Breakdown**

### For a 500,000 row dataset with 30 columns:

1. **Extraction** (30-60 seconds)
   - Fetch all 500K rows from source DB
   - Convert to Python dicts
   - Store in extraction service memory
   - Return via HTTP (large JSON payload)

2. **Orchestrator Receives** (10-20 seconds)
   - Parse JSON response
   - Store 500K dicts in `results` dict
   - Memory: ~2-4 GB

3. **Transform Operations** (5-30 seconds per transform)
   - Join: Create new dicts for joined rows
   - Filter: Iterate through all rows (even if pass-through)
   - Projection: May create new dicts

4. **Destination Remap** (10-20 seconds)
   - Line 555: `remap_rows_to_business_names()` creates NEW dicts
   - Iterates through all 500K rows
   - Creates 500K new dict objects

5. **Database Insert** (20-40 seconds)
   - Convert dicts to row tuples
   - COPY operation (this part is actually fast)

**Total Time**: 75-170 seconds for 500K rows

**Memory Peak**: 4-8 GB

---

## 7. **Cache vs. Execution**

### Important Distinction:

**Preview (uses cache)**:
- Location: `api/views/pipeline.py`
- Uses: `CANVAS_CACHE.preview_node_cache` table
- Limit: 100 rows max per cache entry
- Purpose: Fast UI preview during design

**Execute (NO cache)**:
- Location: `services/migration_service/orchestrator.py`
- Uses: In-memory processing
- Limit: None (all rows)
- Purpose: Actual data migration

**From docs**: "So during a **migration run**, there is **no node cache**. Each run: extract → transform in memory → load."

---

## 8. **Recommendations**

### Immediate Improvements (Low Effort, High Impact):

#### **A. Add Progress Logging**
```python
# In orchestrator.py, line 454
logger.info(f"Extraction completed: {len(data)} rows fetched, memory size: ~{sys.getsizeof(data) / 1024 / 1024:.2f} MB")
```

#### **B. Implement Chunked Processing**
```python
# Modify extraction to support pagination
extraction_request = {
    "chunk_size": 10000,  # Already exists!
    "offset": 0,
    "limit": 10000
}
```

#### **C. Add Memory Monitoring**
```python
import psutil
process = psutil.Process()
logger.info(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
```

### Medium-Term Improvements:

#### **D. Streaming Pipeline**
- Modify orchestrator to process chunks
- Use generators instead of lists
- Process chunk → transform → insert → next chunk

#### **E. Temporary Tables**
- Store intermediate results in temp DB tables
- Reduce memory footprint
- Enable SQL-based transforms

### Long-Term Improvements:

#### **F. Distributed Processing**
- Use Celery for parallel chunk processing
- Message queue for chunk coordination
- Separate workers for extract/transform/load

---

## 9. **Answers to Your Questions**

### Q: "Is it running the data or making the data in the memory and doing the transformation?"

**A**: **Making data in memory and doing transformation**. The entire dataset is:
1. Fetched into memory (extraction service)
2. Transferred to orchestrator memory
3. Transformed in memory (joins, filters, etc.)
4. Only written to DB at the final step

### Q: "In websocket logs there is data in form of dictionary been printed, is the data been passed to db in form of dictionary?"

**A**: **No**. Two different things:
1. **WebSocket logs**: Progress/status messages (small dicts with job metadata)
2. **Database inserts**: Row data converted from dicts to tuples, inserted as normal SQL rows

### Q: "In case of bulk CSV update using copy function explain"

**A**: The COPY function:
1. **Input**: Python list of dicts (in memory)
2. **Conversion**: Dicts → CSV format in StringIO buffer (line 131-135)
3. **Transfer**: `cursor.copy_expert()` streams CSV to PostgreSQL
4. **Insert**: PostgreSQL parses CSV and inserts as rows
5. **Efficiency**: Very fast (10-100x faster than INSERT statements)

**The COPY function is NOT the bottleneck**. The bottleneck is getting data TO the COPY function (all in memory).

---

## 10. **Monitoring Commands**

To diagnose during execution:

```bash
# Monitor Python process memory
ps aux | grep python | grep migration_service

# Monitor PostgreSQL connections
SELECT * FROM pg_stat_activity WHERE application_name LIKE '%migration%';

# Check WebSocket logs
tail -f logs/websocket_server.log

# Check migration service logs  
tail -f logs/migration_service.log
```

---

## Conclusion

The system is slow because it's **memory-bound**, not **I/O-bound**. The bulk insert (COPY) is efficient, but the system loads gigabytes of data into RAM before it can even start inserting. For large datasets, this causes:

1. Memory exhaustion
2. Garbage collection overhead
3. Potential swapping to disk
4. Slow dictionary operations at scale

**Primary Fix**: Implement chunked/streaming processing to keep memory usage constant regardless of dataset size.
