# Pipeline Execution - Complete Guide

## Quick Reference

This guide explains how your data migration pipeline executes when you click the "Execute" button.

---

## 📚 Documentation Index

I've created several detailed documents for you:

1. **`PIPELINE_EXECUTION_EXPLAINED.md`** - Complete walkthrough of execution flow
2. **`EXECUTION_TIMELINE.md`** - Visual timeline with memory usage
3. **`PERFORMANCE_ANALYSIS.md`** - Why the system is slow (memory issues)
4. **`OPTIMIZATION_STRATEGY.md`** - How to fix it (streaming + temp tables)
5. **`OPTIMIZATION_COMPARISON.md`** - Before/after comparison
6. **`temp_table_manager.py`** - Ready-to-use implementation

---

## 🎯 Quick Answer: How Does Execution Work?

### Your Canvas Pipeline

Looking at your canvas:
```
trad_connections (source) → Projection → ┐
                                         ├→ Join → Projection → Compute → dest_pointers
trad_log_updates (source) → Projection → ┘
```

### Execution Levels (Automatic Calculation)

The system automatically calculates execution levels using **topological sort**:

```
Level 0: [trad_connections, trad_log_updates]  ← Both sources run in parallel
Level 1: [projection_1, projection_2]          ← Both projections run in parallel
Level 2: [join]                                 ← Waits for both inputs, then runs
Level 3: [projection_3]                         ← Runs after join
Level 4: [compute]                              ← Runs after projection
Level 5: [dest_pointers]                        ← Loads to database
```

### Execution Rules

1. **Within a level**: Nodes run **in parallel** (asyncio.gather)
2. **Between levels**: Levels run **sequentially** (one after another)
3. **Data flow**: Each node's output stored in `results` dict
4. **Dependencies**: A node only runs when all its inputs are ready

---

## 🔄 Execution Flow (Step-by-Step)

### 1. User Clicks Execute
- **File**: `frontend/src/components/Canvas/DataFlowCanvasChakra.tsx`
- **Function**: `handleExecute()`
- **Action**: Validates canvas, sends nodes/edges to Django API

### 2. Django Creates Job
- **File**: `api/views/migration_views.py`
- **Function**: `MigrationJobViewSet.execute()`
- **Action**: Creates `MigrationJob` record, enqueues Celery task, returns job_id

### 3. Celery Calls Migration Service
- **File**: `api/tasks/migration_tasks.py`
- **Function**: `execute_migration_task()`
- **Action**: Builds config with connections, POSTs to Migration Service

### 4. Migration Service Builds Pipeline
- **File**: `services/migration_service/orchestrator.py`
- **Function**: `build_pipeline()`
- **Action**: Calculates execution levels using topological sort

### 5. Execute Level by Level
- **File**: `services/migration_service/orchestrator.py`
- **Function**: `execute_pipeline()`
- **Action**: For each level, run nodes in parallel, store results

### 6. Each Node Executes
- **Source**: Calls Extraction Service, waits, returns data
- **Transform**: Gets input from results dict, transforms, returns data
- **Destination**: Gets input, remaps columns, bulk inserts to DB

### 7. Progress Updates
- **File**: `services/migration_service/main.py`
- **Function**: `broadcast_update()`
- **Action**: Sends WebSocket updates to frontend for live progress

---

## 💾 Data Flow (In-Memory)

### Results Dictionary

As each node completes, its output is stored:

```python
results = {
    "trad_connections_id": {
        "success": True,
        "data": [1000 rows],  # ← All rows in memory
        "rows_extracted": 1000
    },
    "trad_log_updates_id": {
        "success": True,
        "data": [500 rows],   # ← All rows in memory
        "rows_extracted": 500
    },
    "join_id": {
        "success": True,
        "data": [800 rows],   # ← Joined data in memory
        "stats": {"rows_transformed": 800}
    },
    # ... etc
}
```

### Memory Usage

**Current Architecture**:
- All data loaded into memory
- Stays in memory throughout pipeline
- Peak: 4-8 GB for large datasets
- **This is the performance bottleneck!**

---

## ⚡ Parallel vs Sequential

### Parallel Execution (Within Level)

```python
# Level 0: Both sources run AT THE SAME TIME
tasks = [
    extract_trad_connections(),  # Starts at t=0
    extract_trad_log_updates()   # Starts at t=0
]
results = await asyncio.gather(*tasks)  # Both finish at t=10
# Total time: 10 seconds (NOT 20!)
```

### Sequential Execution (Between Levels)

```python
# Level 0 must complete before Level 1 starts
for level in execution_levels:
    await execute_level(level)  # Waits for completion
    # Then moves to next level
```

---

## 🔗 Join Synchronization

### How Join Waits for Both Inputs

```
Projection 1 completes → Stored in results["projection_1_id"]
Projection 2 completes → Stored in results["projection_2_id"]
                         ↓
                    Level 1 complete
                         ↓
                    Level 2 starts
                         ↓
                    Join node runs
                         ↓
                Gets both inputs from results dict
```

**Code**: `orchestrator.py` line 486-508
```python
# Join node automatically gets both inputs
upstream_list = self._get_all_upstream_data(node, previous_results, config)
left_id, left_data = upstream_list[0]   # From projection_1
right_id, right_data = upstream_list[1]  # From projection_2

# Both are guaranteed to be available because:
# 1. Join is in Level 2
# 2. Both projections are in Level 1
# 3. Level 2 only starts after Level 1 completes
```

---

## 📊 Execution Timeline (Example)

For your canvas with 1000 + 500 rows:

```
t=0s:   Level 0 starts (both sources in parallel)
        - trad_connections: Extracting...
        - trad_log_updates: Extracting...

t=10s:  Level 0 complete, Level 1 starts (both projections in parallel)
        - projection_1: Transforming 1000 rows...
        - projection_2: Transforming 500 rows...

t=15s:  Level 1 complete, Level 2 starts (join)
        - join: Merging 1000 + 500 rows...

t=25s:  Level 2 complete, Level 3 starts (projection)
        - projection_3: Transforming 800 rows...

t=28s:  Level 3 complete, Level 4 starts (compute)
        - compute: Processing 800 rows...

t=32s:  Level 4 complete, Level 5 starts (destination)
        - dest_pointers: Loading 800 rows to PostgreSQL...

t=40s:  Level 5 complete, pipeline done!
        ✓ Success: 800 rows loaded
```

---

## 🎨 WebSocket Updates (What You See in Logs)

The "dictionaries" you see in WebSocket logs are **progress messages**, not row data:

```python
# Example WebSocket message
{
    "type": "status",
    "status": "running",
    "progress": 50.0,
    "current_step": "Level 3/6: running 1 node(s)",
    "current_level": 3,
    "total_levels": 6,
    "level_status": "running"
}

# NOT row data! Just metadata about job progress.
```

---

## 🗄️ Database Insert (COPY Function)

### How Data Gets to Database

```python
# 1. Input: List of dictionaries (in memory)
data = [
    {"id": 1, "name": "Connection A", "status": "active"},
    {"id": 2, "name": "Connection B", "status": "inactive"},
    # ... 800 rows
]

# 2. Convert to row tuples
rows = [
    [1, "Connection A", "active"],
    [2, "Connection B", "inactive"],
    # ...
]

# 3. Convert to CSV in memory
csv_buffer = StringIO()
writer = csv.writer(csv_buffer)
for row in rows:
    writer.writerow(row)

# 4. PostgreSQL COPY (bulk insert - FAST!)
cursor.copy_expert(
    "COPY dest_pointers (id, name, status) FROM STDIN WITH CSV",
    csv_buffer
)
```

**Key Points**:
- Data is NOT stored as JSON/dictionaries in database
- COPY function is very efficient (10-100x faster than INSERT)
- **COPY is NOT the bottleneck** - getting data to COPY is the bottleneck!

---

## ⚠️ Current Performance Issues

### Problem: Everything in Memory

```
Source (1M rows) → Load ALL into memory (4 GB)
                → Transform in memory (4 GB)
                → Join in memory (8 GB peak)
                → Load to DB (4 GB)

Peak Memory: 8 GB
Duration: 120 seconds
Risk: Out of memory errors
```

### Solution: Streaming + Temp Tables

```
Source (1M rows) → Stream in chunks (10 MB)
                → Simple transforms: Stream through (10 MB)
                → Complex transforms: Temp tables (50 MB)
                → Load to DB (10 MB chunks)

Peak Memory: 50 MB
Duration: 40 seconds
Scalability: Handles any dataset size
```

**See `OPTIMIZATION_STRATEGY.md` for implementation details.**

---

## 🛠️ Key Code Locations

### Execution Level Calculation
- **File**: `services/migration_service/orchestrator.py`
- **Function**: `_execution_levels()` (lines 163-191)
- **What**: Topological sort to group nodes into parallel levels

### Pipeline Execution
- **File**: `services/migration_service/orchestrator.py`
- **Function**: `execute_pipeline()` (lines 218-334)
- **What**: Execute levels sequentially, nodes in parallel

### Source Node Execution
- **File**: `services/migration_service/orchestrator.py`
- **Function**: `_execute_source_node()` (lines 393-469)
- **What**: Calls Extraction Service, waits for data

### Join Execution
- **File**: `services/migration_service/orchestrator.py`
- **Function**: `_join_in_memory()` (lines 24-119)
- **What**: In-memory join with column renaming

### Destination Loading
- **File**: `services/migration_service/postgres_loader.py`
- **Function**: `load_data()` (lines 273-427)
- **What**: Bulk insert using PostgreSQL COPY

---

## 🎓 Key Concepts

### 1. Topological Sort
- **Purpose**: Determine execution order based on dependencies
- **Result**: Nodes ordered so all inputs are ready before execution
- **Example**: Sources before transforms, transforms before destinations

### 2. Execution Levels
- **Purpose**: Group independent nodes for parallel execution
- **Rule**: Nodes in same level have no dependencies on each other
- **Benefit**: Faster execution (parallel processing)

### 3. In-Memory Results
- **Current**: All data stored in `results` dict
- **Issue**: High memory usage for large datasets
- **Solution**: Streaming + temp tables (see optimization docs)

### 4. Async Execution
- **Within Level**: `asyncio.gather()` runs nodes in parallel
- **Between Levels**: Sequential (await each level)
- **Benefit**: Efficient use of I/O wait time

---

## 📝 Summary

**How It Works Now**:
1. User clicks Execute
2. Django creates job, enqueues Celery
3. Celery calls Migration Service with config
4. Migration Service calculates execution levels
5. Execute level by level (parallel within, sequential between)
6. Each node stores output in `results` dict (in memory)
7. Progress updates sent via WebSocket
8. Final destination loads data using bulk COPY

**Why It's Slow**:
- All data in memory throughout pipeline
- Large datasets (>100K rows) cause memory pressure
- Python dict overhead is significant

**How to Fix It**:
- Stream data in chunks
- Use temp tables for complex operations (aggregations, joins)
- Let database do heavy lifting
- See `OPTIMIZATION_STRATEGY.md` and `temp_table_manager.py`

---

## 🚀 Next Steps

1. **Understand Current Flow**: Read `PIPELINE_EXECUTION_EXPLAINED.md`
2. **See Timeline**: Review `EXECUTION_TIMELINE.md`
3. **Understand Performance**: Read `PERFORMANCE_ANALYSIS.md`
4. **Plan Optimization**: Review `OPTIMIZATION_STRATEGY.md`
5. **Implement**: Use `temp_table_manager.py` as starting point

The execution plan system (levels, topological sort) is solid and doesn't need to change. The optimization is about **how data flows through the levels**, not the level structure itself!
