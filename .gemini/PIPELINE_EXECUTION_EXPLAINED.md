# Pipeline Execution Plan - How It Works in Current Code

## Your Canvas Example

Looking at your canvas, you have this pipeline structure:

```
Top Branch:
  trad_connections (source) → Projection → Join → Projection → Compute → dest_pointers (destination)
                                           ↑
Bottom Branch:                             |
  trad_log_updates (source) → Projection --+
  
Plus a separate branch:
  New Filter → Projection
```

Let me explain exactly how this executes in your current code.

---

## Step-by-Step Execution Flow

### **Phase 1: User Clicks "Execute" Button**

**Location**: `frontend/src/components/Canvas/DataFlowCanvasChakra.tsx` → `handleExecute()`

```typescript
// 1. Validation
if (!canvasId) {
  toast.error("Please save canvas first");
  return;
}

// 2. Validate joins
const joinValidation = validateJoins(nodes, edges);
if (!joinValidation.isValid) {
  toast.error("Join validation failed");
  return;
}

// 3. Call API
const response = await migrationApi.execute(canvasId, { nodes, edges });
// Response: { job_id: "uuid-string", status: "pending" }

// 4. Switch to monitor view
setActiveView("monitor");
subscribeToJobUpdates(response.job_id);
```

**What happens**: Frontend sends canvas nodes and edges to Django API.

---

### **Phase 2: Django Creates Job and Enqueues Celery Task**

**Location**: `api/views/migration_views.py` → `MigrationJobViewSet.execute()`

```python
def execute(self, request):
    # 1. Get canvas
    canvas_id = request.data.get("canvas_id")
    canvas = Canvas.objects.get(id=canvas_id)
    
    # 2. Create MigrationJob in database
    migration_job = MigrationJob.objects.create(
        job_id=uuid.uuid4(),
        canvas_id=canvas_id,
        customer_id=canvas.customer_id,
        status='pending',
        config={
            "nodes": request.data.get("nodes"),
            "edges": request.data.get("edges")
        }
    )
    
    # 3. Enqueue Celery task (ASYNC - doesn't wait)
    execute_migration_task.delay(migration_job.id)
    
    # 4. Return immediately
    return Response({
        "job_id": str(migration_job.job_id),
        "status": "pending"
    }, status=202)
```

**What happens**: Django creates a job record and tells Celery to process it, then returns immediately.

---

### **Phase 3: Celery Worker Calls Migration Service**

**Location**: `api/tasks/migration_tasks.py` → `execute_migration_task()`

```python
@shared_task(bind=True, max_retries=3)
def execute_migration_task(self, job_id: int):
    # 1. Load job from database
    migration_job = MigrationJob.objects.get(id=job_id)
    canvas = migration_job.canvas
    
    # 2. Update status to 'running'
    migration_job.status = 'running'
    migration_job.started_on = timezone.now()
    migration_job.save()
    
    # 3. Build config with source/destination connections
    config = build_migration_config(canvas, migration_job)
    # config = {
    #   "source_configs": {
    #     "node_1": {"connection_config": {...}},
    #     "node_2": {"connection_config": {...}}
    #   },
    #   "destination_configs": {
    #     "node_5": {"connection_config": {...}, "db_type": "postgresql"}
    #   },
    #   "node_output_metadata": {...}
    # }
    
    # 4. Call Migration Service (FastAPI on port 8003)
    response = requests.post(
        "http://localhost:8003/execute",
        json={
            "job_id": str(migration_job.job_id),
            "canvas_id": canvas.id,
            "nodes": canvas.get_nodes(),
            "edges": canvas.get_edges(),
            "config": config
        }
    )
    
    # 5. Wait for completion (polls status endpoint)
    # ... polling logic ...
    
    # 6. Update job status based on result
    migration_job.status = 'completed'
    migration_job.completed_on = timezone.now()
    migration_job.save()
```

**What happens**: Celery loads connection configs and sends everything to the Migration Service.

---

### **Phase 4: Migration Service Builds Execution Plan**

**Location**: `services/migration_service/main.py` → `execute_migration_pipeline()`

```python
async def execute_migration_pipeline(job_id, canvas_id, nodes, edges, config):
    # 1. Create orchestrator
    orchestrator = MigrationOrchestrator(
        extraction_service_url="http://localhost:8001"
    )
    
    # 2. Build pipeline structure
    pipeline = orchestrator.build_pipeline(nodes, edges)
    
    # This returns:
    # {
    #   "nodes": {node_id: node_data, ...},
    #   "edges": [...],
    #   "execution_order": [node_id1, node_id2, ...],  # Topological sort
    #   "execution_levels": [[level0_nodes], [level1_nodes], ...]  # Parallel groups
    # }
```

---

### **Phase 5: Orchestrator Builds Execution Levels**

**Location**: `services/migration_service/orchestrator.py` → `build_pipeline()`

For your canvas, here's what happens:

#### **Step 5.1: Build Node Map**
```python
node_map = {
    "trad_connections_id": {
        "id": "trad_connections_id",
        "type": "source",
        "data": {"tableName": "trad_connections", ...}
    },
    "trad_log_updates_id": {
        "id": "trad_log_updates_id", 
        "type": "source",
        "data": {"tableName": "trad_log_updates", ...}
    },
    "projection_1_id": {...},
    "projection_2_id": {...},
    "join_id": {...},
    "projection_3_id": {...},
    "compute_id": {...},
    "dest_pointers_id": {...}
}
```

#### **Step 5.2: Build Adjacency List (Graph)**
```python
adjacency = {
    "trad_connections_id": ["projection_1_id"],
    "projection_1_id": ["join_id"],
    "trad_log_updates_id": ["projection_2_id"],
    "projection_2_id": ["join_id"],
    "join_id": ["projection_3_id"],
    "projection_3_id": ["compute_id"],
    "compute_id": ["dest_pointers_id"]
}
```

#### **Step 5.3: Calculate Execution Levels (Topological Sort by Waves)**

**Code**: `orchestrator.py` lines 163-191

```python
def _execution_levels(self, node_map, adjacency):
    # Calculate in-degree (number of incoming edges) for each node
    in_degree = {
        "trad_connections_id": 0,      # No incoming edges
        "trad_log_updates_id": 0,      # No incoming edges
        "projection_1_id": 1,          # 1 incoming (from trad_connections)
        "projection_2_id": 1,          # 1 incoming (from trad_log_updates)
        "join_id": 2,                  # 2 incoming (from both projections)
        "projection_3_id": 1,          # 1 incoming (from join)
        "compute_id": 1,               # 1 incoming (from projection_3)
        "dest_pointers_id": 1          # 1 incoming (from compute)
    }
    
    levels = []
    degree = dict(in_degree)
    
    # Level 0: All nodes with in_degree = 0 (sources)
    level_0 = ["trad_connections_id", "trad_log_updates_id"]
    levels.append(level_0)
    
    # Mark as processed, reduce in_degree of children
    degree["trad_connections_id"] = -1
    degree["trad_log_updates_id"] = -1
    degree["projection_1_id"] -= 1  # Now 0
    degree["projection_2_id"] -= 1  # Now 0
    
    # Level 1: Nodes that now have in_degree = 0
    level_1 = ["projection_1_id", "projection_2_id"]
    levels.append(level_1)
    
    # Mark as processed
    degree["projection_1_id"] = -1
    degree["projection_2_id"] = -1
    degree["join_id"] -= 2  # Now 0 (both inputs ready)
    
    # Level 2: Join can now run
    level_2 = ["join_id"]
    levels.append(level_2)
    
    # Continue...
    degree["join_id"] = -1
    degree["projection_3_id"] -= 1  # Now 0
    
    # Level 3
    level_3 = ["projection_3_id"]
    levels.append(level_3)
    
    # Level 4
    degree["projection_3_id"] = -1
    degree["compute_id"] -= 1  # Now 0
    level_4 = ["compute_id"]
    levels.append(level_4)
    
    # Level 5
    degree["compute_id"] = -1
    degree["dest_pointers_id"] -= 1  # Now 0
    level_5 = ["dest_pointers_id"]
    levels.append(level_5)
    
    return levels
```

**Result for your canvas**:
```python
execution_levels = [
    ["trad_connections_id", "trad_log_updates_id"],  # Level 0: Both sources in parallel
    ["projection_1_id", "projection_2_id"],          # Level 1: Both projections in parallel
    ["join_id"],                                      # Level 2: Join (waits for both inputs)
    ["projection_3_id"],                              # Level 3: Projection after join
    ["compute_id"],                                   # Level 4: Compute
    ["dest_pointers_id"]                              # Level 5: Destination
]
```

---

### **Phase 6: Execute Pipeline Level by Level**

**Location**: `services/migration_service/orchestrator.py` → `execute_pipeline()`

```python
async def execute_pipeline(self, pipeline, config, progress_callback, ...):
    execution_levels = pipeline["execution_levels"]
    results = {}  # Stores output of each node
    
    # Execute each level sequentially
    for level_idx, level in enumerate(execution_levels):
        print(f"Executing Level {level_idx}: {level}")
        
        # Broadcast to UI: "Level X/Y: running N node(s) in parallel"
        await progress_callback(
            f"Level {level_idx + 1}/{len(execution_levels)}: running {len(level)} node(s)",
            (level_idx / len(execution_levels)) * 100
        )
        
        # Run all nodes in this level IN PARALLEL
        tasks = [
            self._execute_single_node(node_id, nodes[node_id], nodes, results, config, edges)
            for node_id in level
        ]
        level_results = await asyncio.gather(*tasks)
        
        # Store results
        for node_id, result in zip(level, level_results):
            results[node_id] = result
            # result = {
            #   "success": True,
            #   "node_id": "...",
            #   "data": [...],  # List of row dicts
            #   "rows_extracted": 1000
            # }
```

**For your canvas, execution goes like this**:

#### **Level 0**: Extract from both sources (parallel)
```python
# Both run at the same time (asyncio.gather)
Task 1: Extract from trad_connections
  → Calls Extraction Service: POST /extract
  → Waits for completion
  → Returns: {"success": True, "data": [1000 rows]}

Task 2: Extract from trad_log_updates
  → Calls Extraction Service: POST /extract
  → Waits for completion
  → Returns: {"success": True, "data": [500 rows]}

# results = {
#   "trad_connections_id": {"success": True, "data": [1000 rows]},
#   "trad_log_updates_id": {"success": True, "data": [500 rows]}
# }
```

#### **Level 1**: Both projections (parallel)
```python
# Both run at the same time
Task 1: Projection on trad_connections data
  → Gets input: results["trad_connections_id"]["data"]
  → Pass-through (current implementation)
  → Returns: {"success": True, "data": [1000 rows]}

Task 2: Projection on trad_log_updates data
  → Gets input: results["trad_log_updates_id"]["data"]
  → Pass-through
  → Returns: {"success": True, "data": [500 rows]}
```

#### **Level 2**: Join (waits for both inputs)
```python
# Only runs after Level 1 completes
Task: Join
  → Gets left input: results["projection_1_id"]["data"]  # 1000 rows
  → Gets right input: results["projection_2_id"]["data"]  # 500 rows
  → Calls _join_in_memory(left, right, join_type, conditions)
  → Returns: {"success": True, "data": [800 rows]}  # After join
```

#### **Level 3**: Projection after join
```python
Task: Projection
  → Gets input: results["join_id"]["data"]  # 800 rows
  → Pass-through
  → Returns: {"success": True, "data": [800 rows]}
```

#### **Level 4**: Compute
```python
Task: Compute
  → Gets input: results["projection_3_id"]["data"]  # 800 rows
  → Pass-through (current implementation)
  → Returns: {"success": True, "data": [800 rows]}
```

#### **Level 5**: Load to destination
```python
Task: Destination
  → Gets input: results["compute_id"]["data"]  # 800 rows
  → Remaps column names to business names
  → Calls PostgresLoader.load_data(...)
  → Uses COPY bulk insert
  → Returns: {"success": True, "rows_loaded": 800}
```

---

### **Phase 7: Node Execution Details**

#### **Source Node Execution**

**Location**: `orchestrator.py` lines 393-469

```python
async def _execute_source_node(self, node, config):
    # 1. Get connection config from Django
    source_configs = config.get("source_configs", {})
    connection_config = source_configs.get(node["id"], {}).get("connection_config")
    
    # 2. Build extraction request
    extraction_request = {
        "source_type": "postgresql",
        "connection_config": connection_config,
        "table_name": "trad_connections",
        "schema_name": None,
        "chunk_size": 10000
    }
    
    # 3. Call Extraction Service
    response = await self.client.post(
        "http://localhost:8001/extract",
        json=extraction_request
    )
    job_id = response.json()["job_id"]
    
    # 4. Wait for extraction to complete
    data = await self._wait_for_extraction(job_id)
    # Polls: GET /extract/{job_id}/status every 2 seconds
    # When status = "completed", fetches: GET /extract/{job_id}/data
    
    # 5. Return data
    return {
        "success": True,
        "node_id": node["id"],
        "data": data,  # List of dicts: [{"col1": val1, "col2": val2}, ...]
        "rows_extracted": len(data)
    }
```

#### **Transform Node Execution (Join)**

**Location**: `orchestrator.py` lines 471-530

```python
async def _execute_transform_node(self, node, previous_results, config):
    node_type = node.get("type")
    
    if node_type == "join":
        # 1. Get both inputs
        upstream_list = self._get_all_upstream_data(node, previous_results, config)
        # upstream_list = [
        #   ("projection_1_id", [1000 rows]),
        #   ("projection_2_id", [500 rows])
        # ]
        
        left_id, left_data = upstream_list[0]
        right_id, right_data = upstream_list[1]
        
        # 2. Get join config
        join_type = node["data"]["config"]["joinType"]  # "INNER"
        conditions = node["data"]["config"]["conditions"]
        # conditions = [
        #   {"leftColumn": "id", "rightColumn": "connection_id", "operator": "="}
        # ]
        
        # 3. Perform in-memory join
        result_data = _join_in_memory(left_data, right_data, join_type, conditions)
        # This iterates through all rows, builds hash index, performs join
        
        # 4. Return joined data
        return {
            "success": True,
            "node_id": node["id"],
            "data": result_data,
            "stats": {"rows_transformed": len(result_data)}
        }
    
    # For projection/filter/compute: pass-through
    else:
        input_data = self._get_input_data(node, previous_results, config)
        return {
            "success": True,
            "node_id": node["id"],
            "data": input_data
        }
```

#### **Destination Node Execution**

**Location**: `orchestrator.py` lines 532-676

```python
async def _execute_destination_node(self, node, previous_results, config):
    # 1. Get input data from upstream
    input_data = self._get_input_data(node, previous_results, config)
    # input_data = [800 rows from compute node]
    
    # 2. Get destination config
    destination_configs = config.get("destination_configs", {})
    dest_config = destination_configs.get(node["id"], {})
    connection_config = dest_config.get("connection_config")
    db_type = dest_config.get("db_type", "postgresql")
    
    # 3. Remap column names (technical → business names)
    node_output_metadata = config.get("node_output_metadata", {})
    upstream_id = "compute_id"  # From edge
    output_metadata = node_output_metadata.get(upstream_id)
    
    if output_metadata:
        input_data = remap_rows_to_business_names(input_data, output_metadata["columns"])
    
    # 4. Get table config
    table_name = node["data"]["config"]["tableName"]  # "dest_pointers"
    schema = node["data"]["config"].get("schema", "")
    load_mode = node["data"]["config"].get("loadMode", "insert")
    
    # 5. Load data
    loader = PostgresLoader()
    result = await loader.load_data(
        data=input_data,
        destination_config=connection_config,
        table_name=table_name,
        schema=schema,
        create_if_not_exists=True,
        drop_and_reload=(load_mode == "drop_and_reload")
    )
    
    # 6. Return result
    return {
        "success": True,
        "node_id": node["id"],
        "rows_loaded": result["rows_loaded"]
    }
```

---

### **Phase 8: Progress Updates to UI**

Throughout execution, the orchestrator broadcasts updates via WebSocket:

```python
# At start of each level
await broadcast_update(job_id, {
    "type": "status",
    "status": "running",
    "progress": 40.0,
    "current_step": "Level 3/6: running 1 node(s)",
    "current_level": 3,
    "total_levels": 6,
    "level_status": "running"
})

# When each node starts
await broadcast_update(job_id, {
    "type": "node_progress",
    "node_id": "join_id",
    "status": "running",
    "progress": 50.0,
    "message": "Processing join_id"
})

# When each node completes
await broadcast_update(job_id, {
    "type": "node_progress",
    "node_id": "join_id",
    "status": "completed",
    "progress": 100.0,
    "message": "Completed"
})
```

The frontend listens to these updates and shows:
- Overall progress bar
- Current level
- Which nodes are running (yellow)
- Which nodes are completed (green checkmark)

---

## Summary: Execution Flow for Your Canvas

```
1. User clicks Execute
   ↓
2. Frontend → Django API
   ↓
3. Django creates MigrationJob, enqueues Celery task
   ↓
4. Celery → Migration Service (FastAPI)
   ↓
5. Migration Service builds execution plan:
   
   Level 0: [trad_connections, trad_log_updates]  ← Extract in parallel
   Level 1: [projection_1, projection_2]          ← Transform in parallel
   Level 2: [join]                                ← Wait for both, then join
   Level 3: [projection_3]                        ← Transform
   Level 4: [compute]                             ← Transform
   Level 5: [dest_pointers]                       ← Load to destination
   
6. Execute level by level:
   - Nodes in same level run in parallel (asyncio.gather)
   - Each level waits for previous level to complete
   - Results stored in `results` dict
   
7. Each node:
   - Source: Calls Extraction Service, waits, returns data
   - Transform: Gets input from results dict, transforms, returns data
   - Destination: Gets input, remaps columns, bulk inserts
   
8. Progress updates sent to WebSocket → Frontend shows live progress

9. On completion:
   - Update MigrationJob status to 'completed'
   - Broadcast final status to UI
   - Show success message
```

---

## Key Points

1. **Topological Sort**: Ensures nodes run in correct dependency order
2. **Execution Levels**: Groups independent nodes for parallel execution
3. **In-Memory Results**: Each node's output stored in `results` dict
4. **Async Execution**: Nodes in same level run concurrently (asyncio.gather)
5. **Sequential Levels**: Levels run one after another (ensures dependencies met)
6. **Join Synchronization**: Join node only runs when BOTH inputs are ready

This is why your join works correctly - it's in Level 2, which only starts after both projections in Level 1 have completed!
