# Pipeline Execution Timeline - Visual Diagram

## Your Canvas Execution Flow

```
TIME →  0s        10s       15s       25s   28s 32s    40s
        │         │         │         │     │   │      │
        ▼         ▼         ▼         ▼     ▼   ▼      ▼

LEVEL 0 ┌─────────────────┐
(Parallel) │ trad_connections│ ← Extracting 1000 rows
        │    (Source)     │
        └─────────────────┘
        
        ┌─────────────────┐
        │ trad_log_updates│ ← Extracting 500 rows
        │    (Source)     │
        └─────────────────┘
                  │
                  │ Both complete at t=10s
                  ▼
                  
LEVEL 1           ┌─────────┐
(Parallel)        │Projection│ ← Transform 1000 rows
                  │    1    │
                  └─────────┘
                  
                  ┌─────────┐
                  │Projection│ ← Transform 500 rows
                  │    2    │
                  └─────────┘
                        │
                        │ Both complete at t=15s
                        ▼
                        
LEVEL 2                 ┌──────────────┐
(Single)                │     Join     │ ← Merge 1000 + 500 rows
                        │   (INNER)    │   Result: 800 rows
                        └──────────────┘
                              │
                              │ Complete at t=25s
                              ▼
                              
LEVEL 3                       ┌─────────┐
(Single)                      │Projection│ ← Transform 800 rows
                              │    3    │
                              └─────────┘
                                    │
                                    │ Complete at t=28s
                                    ▼
                                    
LEVEL 4                             ┌────────┐
(Single)                            │ Compute│ ← Process 800 rows
                                    └────────┘
                                          │
                                          │ Complete at t=32s
                                          ▼
                                          
LEVEL 5                                   ┌──────────────┐
(Single)                                  │dest_pointers │ ← Load 800 rows
                                          │(Destination) │   to PostgreSQL
                                          └──────────────┘
                                                │
                                                │ Complete at t=40s
                                                ▼
                                          ✓ PIPELINE COMPLETE
```

---

## Results Dictionary (In-Memory Storage)

As each node completes, its output is stored in the `results` dict:

```python
results = {
    # After Level 0 completes (t=10s):
    "trad_connections_id": {
        "success": True,
        "node_id": "trad_connections_id",
        "data": [
            {"id": 1, "name": "Connection A", "status": "active"},
            {"id": 2, "name": "Connection B", "status": "inactive"},
            # ... 1000 rows total
        ],
        "rows_extracted": 1000
    },
    
    "trad_log_updates_id": {
        "success": True,
        "node_id": "trad_log_updates_id",
        "data": [
            {"connection_id": 1, "update_time": "2024-01-01", "log": "Updated"},
            {"connection_id": 2, "update_time": "2024-01-02", "log": "Created"},
            # ... 500 rows total
        ],
        "rows_extracted": 500
    },
    
    # After Level 1 completes (t=15s):
    "projection_1_id": {
        "success": True,
        "node_id": "projection_1_id",
        "data": [
            {"id": 1, "name": "Connection A", "status": "active"},
            # ... 1000 rows (pass-through in current implementation)
        ],
        "stats": {"rows_transformed": 1000}
    },
    
    "projection_2_id": {
        "success": True,
        "node_id": "projection_2_id",
        "data": [
            {"connection_id": 1, "update_time": "2024-01-01", "log": "Updated"},
            # ... 500 rows (pass-through)
        ],
        "stats": {"rows_transformed": 500}
    },
    
    # After Level 2 completes (t=25s):
    "join_id": {
        "success": True,
        "node_id": "join_id",
        "data": [
            {
                "id": 1, 
                "name": "Connection A", 
                "status": "active",
                "connection_id": 1,  # Note: May be renamed to connection_id_r
                "update_time": "2024-01-01",
                "log": "Updated"
            },
            # ... 800 rows (inner join result)
        ],
        "stats": {"rows_transformed": 800}
    },
    
    # After Level 3 completes (t=28s):
    "projection_3_id": {
        "success": True,
        "node_id": "projection_3_id",
        "data": [
            # ... 800 rows (pass-through)
        ],
        "stats": {"rows_transformed": 800}
    },
    
    # After Level 4 completes (t=32s):
    "compute_id": {
        "success": True,
        "node_id": "compute_id",
        "data": [
            # ... 800 rows (pass-through or computed)
        ],
        "stats": {"rows_transformed": 800}
    },
    
    # After Level 5 completes (t=40s):
    "dest_pointers_id": {
        "success": True,
        "node_id": "dest_pointers_id",
        "rows_loaded": 800
    }
}
```

---

## Parallel vs Sequential Execution

### Parallel Execution (Within a Level)

```
Level 0: Both sources run AT THE SAME TIME
┌──────────────────┐     ┌──────────────────┐
│ trad_connections │     │ trad_log_updates │
│   Extracting...  │     │   Extracting...  │
└──────────────────┘     └──────────────────┘
        ↓                         ↓
    t=0 to t=10             t=0 to t=10
    
Both start at t=0, both finish around t=10
Total time: 10 seconds (NOT 20 seconds!)
```

**Code**: `orchestrator.py` line 283-287
```python
# Run all nodes in this level in parallel
tasks = [
    self._execute_single_node(node_id, ...)
    for node_id in level
]
level_results = await asyncio.gather(*tasks)  # ← Parallel execution
```

### Sequential Execution (Between Levels)

```
Level 0 completes → Level 1 starts
Level 1 completes → Level 2 starts
Level 2 completes → Level 3 starts
...

┌─────────┐
│ Level 0 │ t=0 to t=10
└─────────┘
     ↓ (waits for completion)
┌─────────┐
│ Level 1 │ t=10 to t=15
└─────────┘
     ↓ (waits for completion)
┌─────────┐
│ Level 2 │ t=15 to t=25
└─────────┘
```

**Code**: `orchestrator.py` line 259-326
```python
for level_idx, level in enumerate(execution_levels):
    # Execute this level
    level_results = await asyncio.gather(*tasks)
    
    # Store results
    for node_id, result in zip(level, level_results):
        results[node_id] = result
    
    # Now move to next level (sequential)
```

---

## Join Node Synchronization

The join node demonstrates why levels are important:

```
Projection 1 (1000 rows) ──┐
                           ├──► Join (waits for BOTH)
Projection 2 (500 rows) ───┘

Timeline:
t=10: Projection 1 starts
t=10: Projection 2 starts (parallel)
t=15: Projection 1 completes
t=15: Projection 2 completes
t=15: Join can NOW start (both inputs ready)
t=25: Join completes
```

**Why this works**:
1. Join has `in_degree = 2` (two incoming edges)
2. Join is placed in Level 2 (after both projections)
3. Level 2 only starts when Level 1 is complete
4. Therefore, both inputs are guaranteed to be in `results` dict

**Code**: `orchestrator.py` line 486-508
```python
if node_type == "join":
    # Get both inputs from results dict
    upstream_list = self._get_all_upstream_data(node, previous_results, config)
    
    left_id, left_data = upstream_list[0]   # From projection_1
    right_id, right_data = upstream_list[1]  # From projection_2
    
    # Both are available because Level 1 completed before Level 2 started
    result_data = _join_in_memory(left_data, right_data, join_type, conditions)
```

---

## Memory Usage Over Time

```
Time →  0s    10s   15s   25s   28s   32s   40s
        │     │     │     │     │     │     │
Memory  │     │     │     │     │     │     │
(GB)    │     │     │     │     │     │     │
        │     │     │     │     │     │     │
8 GB    │     │     │     ┌─────┐           │  ← Peak at join (both sides in memory)
        │     │     │     │     │           │
6 GB    │     │     │     │     │           │
        │     │     │     │     │           │
4 GB    │     ┌─────┼─────┼─────┼─────┬─────┤  ← Source data + transforms
        │     │     │     │     │     │     │
2 GB    │     │     │     │     │     │     │
        │     │     │     │     │     │     │
0 GB    ┴─────┴─────┴─────┴─────┴─────┴─────┴
        
Legend:
- Level 0-1: 4 GB (1000 + 500 rows in results dict)
- Level 2: 8 GB peak (join needs both sides + creates new joined data)
- Level 3-5: 4 GB (joined data flows through)
```

**This is why we need optimization!** The memory stays high throughout the entire pipeline.

---

## WebSocket Updates Timeline

```
t=0s:   {"type": "status", "current_step": "Level 1/6: running 2 nodes", "progress": 0}
        {"type": "node_progress", "node_id": "trad_connections_id", "status": "running"}
        {"type": "node_progress", "node_id": "trad_log_updates_id", "status": "running"}

t=10s:  {"type": "node_progress", "node_id": "trad_connections_id", "status": "completed"}
        {"type": "node_progress", "node_id": "trad_log_updates_id", "status": "completed"}
        {"type": "status", "current_step": "Level 2/6: running 2 nodes", "progress": 16.7}
        {"type": "node_progress", "node_id": "projection_1_id", "status": "running"}
        {"type": "node_progress", "node_id": "projection_2_id", "status": "running"}

t=15s:  {"type": "node_progress", "node_id": "projection_1_id", "status": "completed"}
        {"type": "node_progress", "node_id": "projection_2_id", "status": "completed"}
        {"type": "status", "current_step": "Level 3/6: running 1 node", "progress": 33.3}
        {"type": "node_progress", "node_id": "join_id", "status": "running"}

t=25s:  {"type": "node_progress", "node_id": "join_id", "status": "completed"}
        {"type": "status", "current_step": "Level 4/6: running 1 node", "progress": 50.0}
        {"type": "node_progress", "node_id": "projection_3_id", "status": "running"}

t=28s:  {"type": "node_progress", "node_id": "projection_3_id", "status": "completed"}
        {"type": "status", "current_step": "Level 5/6: running 1 node", "progress": 66.7}
        {"type": "node_progress", "node_id": "compute_id", "status": "running"}

t=32s:  {"type": "node_progress", "node_id": "compute_id", "status": "completed"}
        {"type": "status", "current_step": "Level 6/6: running 1 node", "progress": 83.3}
        {"type": "node_progress", "node_id": "dest_pointers_id", "status": "running"}

t=40s:  {"type": "node_progress", "node_id": "dest_pointers_id", "status": "completed"}
        {"type": "complete", "status": "completed", "progress": 100}
```

The frontend listens to these and updates the UI:
- Progress bar moves from 0% → 100%
- Nodes turn yellow (running) → green (completed)
- Current level indicator updates

---

## Code Flow Summary

```
1. Frontend: handleExecute()
   ↓
2. Django: MigrationJobViewSet.execute()
   - Creates MigrationJob
   - Enqueues Celery task
   ↓
3. Celery: execute_migration_task()
   - Builds config with connections
   - POSTs to Migration Service
   ↓
4. Migration Service: execute_migration_pipeline()
   - Creates orchestrator
   - Builds pipeline
   ↓
5. Orchestrator: build_pipeline()
   - Calculates execution levels
   - Returns: {execution_levels: [[...], [...], ...]}
   ↓
6. Orchestrator: execute_pipeline()
   - For each level:
     - Run nodes in parallel (asyncio.gather)
     - Store results in dict
     - Broadcast progress to WebSocket
   ↓
7. Each node execution:
   - Source: Extract from DB
   - Transform: Get input from results, transform, return
   - Destination: Get input, remap, bulk insert
   ↓
8. Completion:
   - Update MigrationJob status
   - Broadcast complete to WebSocket
   - Frontend shows success
```

---

## Key Takeaways

1. **Execution Levels** = Waves of parallel execution
2. **Topological Sort** = Ensures correct dependency order
3. **In-Memory Results** = All data stored in `results` dict (memory issue!)
4. **Parallel Within Level** = Multiple nodes run simultaneously
5. **Sequential Between Levels** = Levels run one after another
6. **Join Synchronization** = Automatically handled by level system

This is the current architecture. The optimization strategy (temp tables, streaming) will change how data flows through the pipeline while keeping the same level-based execution structure!
