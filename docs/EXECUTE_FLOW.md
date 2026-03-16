# How Execute Works (End-to-End)

When you click **Execute** on the canvas, the following flow runs.

---

## 1. Frontend (Canvas)

**Where:** `frontend/src/components/Canvas/DataFlowCanvasChakra.tsx` → `handleExecute`

**What happens:**

1. **Pre-checks**
   - Canvas must be saved (`canvasId` present); otherwise a toast asks to save first.
   - Join nodes are validated (left/right inputs and join conditions).
   - `handleValidate()` runs; if there are validation errors, execution is blocked.

2. **Request**
   - Edges are normalized to include `sourceHandle` and `targetHandle` (needed for Join nodes).
   - `migrationApi.execute(canvasId, { nodes, edges })` is called.
   - That sends **POST** to `/api/migration-jobs/execute/` with body:
     - `canvas_id`: saved canvas ID
     - `nodes`: list of nodes (id, type, data including config)
     - `edges`: list of edges (source, target, sourceHandle, targetHandle)

3. **Response**
   - Backend returns **202 Accepted** with `job_id` (UUID string).
   - UI switches to **monitor** view and subscribes to WebSocket updates for that `job_id` to show progress.

---

## 2. Django API (Migration Job Create + Celery Enqueue)

**Where:** `api/views/migration_views.py` → `MigrationJobViewSet.execute`

**What happens:**

1. **Validation**
   - Request body is validated with `MigrationJobCreateSerializer` (e.g. `canvas_id` required).

2. **Load canvas**
   - `Canvas.objects.get(id=canvas_id, is_active=True)`; customer is taken from the canvas.

3. **Create job in DB**
   - A `MigrationJob` row is created in the Django DB (`migration_job` table) with:
     - `job_id` (UUID), `canvas_id`, `customer_id`, `status='pending'`, `config`, etc.
   - If the `migration_job` table is missing, the view creates it (via `ensure_migration_job_tables`) and retries the insert.

4. **Enqueue Celery task**
   - `execute_migration_task.delay(migration_job.id)` is called.
   - The HTTP handler returns immediately with **202** and `job_id` (the UUID the frontend uses for monitoring). It does **not** wait for the migration to finish.

5. **No direct call to Migration Service from the view**
   - The Django view does **not** call the Migration Service (port 8003). Only the Celery task does (see below).

---

## 3. Celery Task (Async Worker)

**Where:** `api/tasks/migration_tasks.py` → `execute_migration_task`

**What happens:**

1. **Load job**
   - `MigrationJob.objects.get(id=job_id)` and get the associated canvas.

2. **Update job state**
   - Set `status='running'`, `started_on=now()`, save; create a `MigrationJobLog` “started” entry.

3. **Call Migration Service**
   - **POST** to `http://localhost:8003/execute` with:
     - `canvas_id`
     - `nodes`: from `canvas.get_nodes()` (saved canvas nodes)
     - `edges`: from `canvas.get_edges()` (saved canvas edges)
     - `config`: from the migration job’s config
   - The task uses `asyncio.run(call_migration_service())` and waits for the HTTP response.

4. **On success**
   - Set `status='completed'`, `completed_on`, `stats`, `progress=100`, save; log “completed”.

5. **On failure**
   - Set `status='failed'`, `error_message`, save; log “failed”; task may retry with backoff.

So the **actual pipeline execution** is done by the Migration Service; Celery only triggers it and then updates the Django `MigrationJob` from the result.

---

## 4. Migration Service (FastAPI, port 8003)

**Where:** `services/migration_service/main.py`

**What happens:**

1. **POST /execute**
   - Receives `MigrationRequest`: `canvas_id`, `nodes`, `edges`, `config`.
   - Generates a new **service-level** `job_id` (UUID) and stores it in memory (`migration_jobs[job_id]`).
   - Schedules `execute_migration_pipeline(...)` as a **background task** and returns **202** with that `job_id` and “Migration job started”.

2. **Background: `execute_migration_pipeline`**
   - Sets job status to `running`, “Initializing”.
   - Creates a `MigrationOrchestrator` (points to Extraction Service at `http://localhost:8001`).
   - **Builds pipeline:** `orchestrator.build_pipeline(nodes, edges)`:
     - Builds node map and adjacency from edges.
     - Finds source nodes (no incoming edges).
     - Computes execution order (topological sort) and **execution levels** (nodes in the same level can run in parallel).
   - **Runs pipeline:** `orchestrator.execute_pipeline(pipeline, config, progress_callback)`:
     - For each **level**, runs all nodes in that level in parallel (`asyncio.gather`).
     - For each node, calls `_execute_single_node`:
       - **source** → `_execute_source_node`: calls Extraction Service (e.g. `/extract`), waits for completion, returns extracted data.
       - **transform** → `_execute_transform_node`: gets input from previous results, currently pass-through.
       - **destination** → `_execute_destination_node`: gets input data, uses `HanaLoader` to load into destination (HANA); in current code, connection details may be placeholders.
   - Progress is reported via callbacks and broadcast to the WebSocket service (e.g. `http://localhost:8004`) so the UI can show live progress.
   - On success: sets job to `completed`, `progress=100`, stores `stats`, broadcasts “complete”.
   - On failure: sets job to `failed`, stores error, broadcasts “error”.

So when you click Execute, the **orchestration** (order of nodes, parallel levels, extraction → transform → load) is done here; the Extraction Service and HANA loader do the real I/O.

---

## 5. Migration Orchestrator (Pipeline Execution)

**Where:** `services/migration_service/orchestrator.py`

**Responsibilities:**

- **build_pipeline(nodes, edges)**  
  Builds execution order and levels from the graph (topological sort + level grouping for parallel execution).

- **execute_pipeline(pipeline, config, progress_callback)**  
  For each level, runs `_execute_single_node` for every node in that level in parallel, then moves to the next level. Calls:
  - **Source nodes:** Extraction Service (`/extract`), then poll until done and use extracted data as “previous results” for downstream nodes.
  - **Transform nodes:** Take input from previous results; current implementation is pass-through.
  - **Destination nodes:** Take input from previous results, call `HanaLoader.load_data(...)` to write to the destination.

- **Progress**  
  Invokes `progress_callback(step, progress)` and the service broadcasts updates to the WebSocket server so the dashboard can show progress.

---

## 6. Summary Diagram

```
[User clicks Execute]
        │
        ▼
[DataFlowCanvasChakra: handleExecute]
  • Validate canvas saved, joins, pipeline
  • POST /api/migration-jobs/execute/  { canvas_id, nodes, edges }
        │
        ▼
[Django: MigrationJobViewSet.execute]
  • Create MigrationJob in DB (pending)
  • Celery: execute_migration_task.delay(migration_job.id)
  • Return 202 + job_id (UUID)
        │
        ▼
[Celery worker: execute_migration_task]
  • Load job & canvas
  • Set job running, log start
  • POST http://localhost:8003/execute  { canvas_id, nodes, edges, config }
  • Wait for response
  • On response: set job completed/failed, save & log
        │
        ▼
[Migration Service: POST /execute]
  • Store job in memory, return 202
  • Background: execute_migration_pipeline
        │
        ▼
[Orchestrator: build_pipeline → execute_pipeline]
  • Topological sort + levels (parallel by level)
  • For each level: run source / transform / destination nodes
  • Source → Extraction Service (8001); Destination → HanaLoader
  • Progress → WebSocket (8004) → UI
```

---

## 7. Important URLs / Ports

| Component              | URL / Port        | Role                          |
|------------------------|-------------------|-------------------------------|
| Django API             | e.g. 8000         | Create job, enqueue Celery    |
| Celery worker          | —                 | Calls Migration Service       |
| Migration Service      | http://localhost:8003 | Runs pipeline, levels, nodes |
| Extraction Service     | http://localhost:8001 | Extract data from sources  |
| WebSocket server       | http://localhost:8004 | Live progress to UI       |

---

## 8. Two different `job_id`s

- **Django `MigrationJob.job_id`**  
  UUID returned by the API and used by the frontend for polling/WebSocket (e.g. “monitor” view and job list). Stored in DB.

- **Migration Service in-memory `job_id`**  
  Another UUID generated inside the Migration Service when it receives POST `/execute`. Used only inside that service for in-memory state and WebSocket broadcasts.

The frontend and Django use the **Django job_id**; the Migration Service uses its own id for its internal state and progress broadcasts.
