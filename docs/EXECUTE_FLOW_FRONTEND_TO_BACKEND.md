# Execute Flow: Frontend → Backend → All Services

This document traces the full path when the user clicks **Execute** on the canvas, and how the earlier errors (source_configs missing, destination user None) were fixed.

---

## 1. Frontend (React)

**Where:** `frontend/src/components/Canvas/DataFlowCanvasChakra.tsx` → `handleExecute`

**Flow:**
1. User clicks **Execute** (canvas must be saved so `canvasId` exists).
2. Validation: join nodes have both inputs and conditions; optional server-side `metadataApi.validatePipeline(payload.nodes, payload.edges)`.
3. **API call:** `migrationApi.execute(canvasId, { nodes, edges })`.
   - **Route:** `POST ${API_BASE}/migration-jobs/execute/` (see `frontend/src/constants/server-routes.ts`).
   - **Payload:** `{ canvas_id, nodes, edges }` (no `config` in request; backend builds it).

**Note:** Nodes/edges in the request are not used for execution; the **Celery task** uses the **saved** canvas (`canvas.get_nodes()`, `canvas.get_edges()`). The request mainly triggers the job and passes `canvas_id`.

---

## 2. Django API (Execute action)

**Where:** `api/views/migration_views.py` → `MigrationJobViewSet.execute`

**Flow:**
1. **Validate:** `MigrationJobCreateSerializer` → `canvas_id` (required), `config` (optional, default `{}`).
2. **Load:** `Canvas.objects.get(id=canvas_id)`, `customer = canvas.customer`.
3. **Build config (fix for source/destination configs):**
   - `config = build_migration_config(canvas, customer, config)` from `api/utils/migration_config_builder.py`.
   - Reads **source** nodes → for each, gets `sourceId` from `node.data.config`, fetches from **GENERAL.source** (customer DB or default DB), decrypts, maps to extraction format → `config["source_configs"][node_id] = { "connection_config": { host, port, database, username, password, schema } }`.
   - Reads **destination** nodes → for each, gets `destinationId` from `node.data.config`, fetches from **GENERAL.destination** (same DB), decrypts, maps to loader format → `config["destination_configs"][node_id] = { "connection_config": { host, port, username, password, database, schema } }`.
4. **Create job:** `MigrationJob.objects.create(..., config=config)` so the job stores the built config (with `source_configs` and `destination_configs`).
5. **Trigger task:** `execute_migration_task.delay(migration_job.id)` (or background thread if Celery/Redis unavailable).
6. **Response:** `202 Accepted` with `{ job_id, status: "pending", message }`.

---

## 3. Celery Task (Migration execution)

**Where:** `api/tasks/migration_tasks.py` → `execute_migration_task`

**Flow:**
1. Load `MigrationJob` by `job_id` (Django job PK), then `canvas = job.canvas`, `customer = canvas.customer`.
2. **Re-build config (redundant but safe):** `config = build_migration_config(canvas, customer, job.config or {})`. Ensures `source_configs` and `destination_configs` are present even if view didn’t persist them (e.g. DB error).
3. **Call Migration Service:** `POST http://localhost:8003/execute` with:
   - `canvas_id`, `nodes = canvas.get_nodes()`, `edges = canvas.get_edges()`, `config` (with `source_configs` and `destination_configs`), `job_id = job.job_id` (so WebSocket uses same ID).
4. **Poll status:** Every 2s, `GET http://localhost:8003/{job.job_id}/status` until status is `completed`, `failed`, or `cancelled`; update Django `MigrationJob` (status, progress, current_step, error_message, stats).

---

## 4. Migration Service (FastAPI, port 8003)

**Where:** `services/migration_service/main.py`

**Flow:**
1. **POST /execute:** Accepts `MigrationRequest` (canvas_id, nodes, edges, config, optional job_id). Creates in-memory job, returns `202` with `job_id`.
2. **Background:** `execute_migration_pipeline(job_id, canvas_id, nodes, edges, config)`.
3. **Orchestrator:** `MigrationOrchestrator(extraction_service_url=EXTRACTION_SERVICE_URL)`, `pipeline = orchestrator.build_pipeline(nodes, edges)`, then `orchestrator.execute_pipeline(pipeline, config, progress_callback)`.
4. **Progress:** Updates `migration_jobs[job_id]` and broadcasts to WebSocket (`POST http://localhost:8004/broadcast/{job_id}`).
5. **Result:** If any node fails → set job status `FAILED` and broadcast error; else `COMPLETED`.

---

## 5. Orchestrator (Migration Service)

**Where:** `services/migration_service/orchestrator.py`

**Flow:**
1. **Execution order:** Topological sort + execution levels; nodes in the same level run in parallel.
2. **Per node:**
   - **Source** (`node_type == "source"`): `_execute_source_node(node, config)`.
     - **Connection config (fix):** `connection_config = config["source_configs"][node_id]["connection_config"]`. If missing → returns error: *"Source connection_config is required (host, port, database, username, password). Ensure the migration is started with source_configs..."*.
     - **Extraction:** `POST {extraction_service_url}/extract` with `source_type`, `connection_config`, `table_name`, `schema_name`, `chunk_size`, optional `filter_spec`.
     - **Wait:** `_wait_for_extraction(job_id)` polling `GET {extraction_service_url}/extract/{job_id}/status`.
   - **Transform** (filter, join, projection, etc.): `_execute_transform_node` → pass-through (first previous result with `data`).
   - **Destination** (`destination`, `destination-postgresql`, etc.): `_execute_destination_node(node, previous_results, config)`.
     - **Destination config (fix):** `dest_config = config["destination_configs"][node_id]["connection_config"]` (or by `destination_id`). Passed to `HanaLoader.load_data(..., destination_config=dest_config)`.
     - If no config, loader skips connect and returns `rows_loaded: 0` (no more `user must be string, not NoneType`).

---

## 6. Extraction Service (port 8001)

**Where:** `services/extraction_service/main.py`, workers, connectors

**Flow:**
1. **POST /extract:** Receives `connection_config`, `table_name`, `schema_name`, `chunk_size`, optional `filter_spec`. Validates `connection_config` (host, port, database, username, password).
2. Starts extraction job (in-memory or worker), returns `{ job_id }`.
3. Connector (e.g. `PostgreSQLConnector`) connects to **source DB** using `connection_config`, runs SELECT (with optional WHERE from `filter_spec`), streams rows.
4. **GET /extract/{job_id}/status:** Returns status (running, completed, failed). Orchestrator polls until completed.

---

## 7. WebSocket Server (port 8004)

**Where:** `services/websocket_server/main.py`

**Flow:**
1. Migration service calls `POST /broadcast/{job_id}` with status/progress/error payload.
2. Server emits to all clients in room `job:{job_id}`.
3. Frontend (Jobs page or Canvas monitor) subscribes with `join_job` and receives status updates (fix: CORS list includes localhost origins to avoid 403 on connect).

**Verification:** In Django/Celery logs, look for `build_migration_config: done. source_configs=N, destination_configs=M`; N should match the number of source nodes. If the Migration Service receives config without source_configs for a source node, it logs: `[MIGRATION] config.source_configs missing for source node(s) ...; extraction will not be triggered`.

---

## Summary of Fixes Applied

| Issue | Fix |
|-------|-----|
| **Source: "connection_config is required"** | `build_migration_config()` in view and task: read GENERAL.source by sourceId, decrypt, fill `config["source_configs"][node_id]`. View saves this in job.config; task re-builds and sends to migration service. |
| **Destination: "user must be string, not NoneType"** | (1) Orchestrator reads `config["destination_configs"][node_id]["connection_config"]` and passes to loader. (2) `build_migration_config()` now also fills `config["destination_configs"]` from GENERAL.destination by destinationId. (3) HanaLoader: skip connect when no config/host; use `user = config.get("user") or config.get("username") or ""` so never pass None. |
| **HanaLoader not defined** | Added `from hana_loader import HanaLoader` in `orchestrator.py`. |
| **WebSocket 403** | Socket.IO server uses explicit `cors_allowed_origins` list (localhost:5173, 3000, 4200, 8004, etc.) so engineio accepts the connection. |

---

## Config Storage (where credentials live)

- **Source configs:** Table `"GENERAL".source` in **customer DB** (`customer.cust_db`), column `source_config` / `dest_config` (encrypted). Keyed by source connection `id`; canvas nodes reference it via `node.data.config.sourceId`.
- **Destination configs:** Table `"GENERAL".destination` in **customer DB**, column `destination_config` / `dest_config` (encrypted). Keyed by destination `id`; canvas nodes reference it via `node.data.config.destinationId`.
- **Migration job config:** Django `MigrationJob.config` (JSON) holds the **built** payload: `source_configs`, `destination_configs` (and any other keys). This is what gets sent to the migration service; credentials are decrypted at build time and not re-persisted in plain form.
