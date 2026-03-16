# Migration Execution, Node Cache, and Destination Tables — Developer Guide

This document explains **how pipeline nodes run**, **where and when node cache is used**, and **how destination tables are created**. It is written so a new developer can follow the full flow from "Execute" click to data in the destination database.

---

## 1. Two Different Flows: Preview vs Migration Run

The codebase has **two separate execution paths**:

| Aspect | **Preview** (design-time) | **Migration run** (Execute button) |
|--------|---------------------------|-------------------------------------|
| **Trigger** | User previews a node (e.g. "Preview" on a filter or join) | User clicks "Execute" on the canvas |
| **Backend** | Django API (`api/views/pipeline.py`) | FastAPI Migration Service (`services/migration_service/main.py`) |
| **Execution** | SQL compiler runs against **customer DB**; optional **node cache** (DB) | **Orchestrator** runs in memory: extraction → transform → load |
| **Node cache** | **Yes** — checkpoint cache in `CANVAS_CACHE.preview_node_cache` | **No** — each run fetches and transforms data again |
| **Output** | Rows returned to UI for preview | Data written to **destination** (PostgreSQL or HANA) |

So:

- **Preview** = "Show me what this node’s output looks like" → uses **SQL + optional cache** in Django.
- **Migration run** = "Actually move data to the destination" → uses **orchestrator + loaders**, no cache.

---

## 2. How a Migration Run Works (Execute Button)

When the user clicks **Execute**, this is the path:

```
Frontend (Execute) 
  → Django: create MigrationJob, enqueue Celery task 
    → Celery: execute_migration_task(job_id) 
      → HTTP POST to FastAPI: POST /execute (job_id, canvas_id, nodes, edges, config)
        → FastAPI: run pipeline in background_tasks
          → Orchestrator.execute_pipeline(...)
```

### 2.1 Who does what

- **Django** (`api/views/migration_views.py`): Creates a `MigrationJob`, builds `config` (e.g. `source_configs`, `destination_configs`, `node_output_metadata`), then calls `execute_migration_task.delay(migration_job.id)` and returns immediately with `job_id`.
- **Celery** (`api/tasks/migration_tasks.py`): Loads the job and canvas, optionally fills `node_output_metadata` (for destination column remap), then **POSTs once** to the FastAPI service at `http://localhost:8003/execute` with `job_id`, `canvas_id`, `nodes`, `edges`, `config`.
- **FastAPI** (`services/migration_service/main.py`): Registers the job, runs `orchestrator.execute_pipeline(...)` in a **background task**, and returns **202 Accepted** with `job_id`. The UI (and optional Celery poll task) gets status via `GET /{job_id}/status` or **WebSocket** broadcasts.

So: **nodes do not run in Django**. They run inside the **Migration Service** (FastAPI), in the **orchestrator**.

---

## 3. How Nodes Run Inside the Orchestrator

The orchestrator lives in **`services/migration_service/orchestrator.py`**.

### 3.1 Pipeline structure

- **Nodes** and **edges** define a directed graph (e.g. Source → Filter → Join → Projection → Destination).
- The orchestrator:
  1. Builds **execution levels** (waves of nodes that can run in parallel).
  2. Runs **one level at a time**; within a level, nodes run **in parallel** (`asyncio.gather`).
  3. Each node’s result is stored in a **`results`** dict (key = node_id). Downstream nodes read from `results` to get their input.

### 3.2 Execution levels (topological order)

- **Level 0**: All **source** nodes (no incoming edges).
- **Level 1**: Nodes whose **only** predecessors are in level 0 (e.g. filters/projections that depend only on sources).
- **Level 2**: Next layer (e.g. a **join** after two branches; it runs only when both inputs are ready).
- … and so on until **destination** nodes.

So execution order is **topological**: a node runs only after all its upstream nodes have completed and written to `results`.

### 3.3 What each node type does

- **Source**  
  - **Input**: None (config has `source_configs`, `tableName`, etc.).  
  - **Action**: Calls the **Extraction Service** (`POST /extract`), waits for the job to finish, then fetches rows.  
  - **Output**: `{ "success": True, "node_id": "...", "data": [ {...}, ... ] }`.  
  - **No cache**: Data is fetched from the source system every run.

- **Filter / Projection / Compute (transform)**  
  - **Input**: Data from **direct upstream** node(s) via `_get_input_data()` or, for join, `_get_all_upstream_data()` (left + right).  
  - **Action**:  
    - **Join**: Merges left and right in memory (`_join_in_memory`). Column naming: base names; if both sides have the same name, use `_l` / `_r` suffix.  
    - **Filter / Projection / Compute**: Currently **pass-through** — they take the first upstream’s `data` and return it (no in-memory filter/projection/expression in the migration service; those are applied in **preview** via SQL).  
  - **Output**: Same shape: `{ "success": True, "node_id": "...", "data": [ ... ] }`.  
  - **No cache**: All in memory for this run.

- **Destination**  
  - **Input**: Data from the **single direct upstream** node (the one connected by an edge into this destination).  
  - **Action**:  
    1. Optionally **remap** row keys from technical/db names to **business (display) names** using `config["node_output_metadata"][upstream_id]`.  
    2. Call **PostgresLoader** or **HanaLoader** with the (possibly remapped) list of row dicts.  
  - **Output**: `{ "success": True, "node_id": "...", "rows_loaded": N }`.  
  - **No cache**: Writes directly to the destination DB.

So during a **migration run**, there is **no node cache**. Each run: extract → transform in memory → load.

---

## 4. Node Cache (Preview Only)

Node cache is used **only in the preview path** (Django + SQL compiler), not in the migration orchestrator.

### 4.1 Where it lives

- **Single table**: `CANVAS_CACHE.preview_node_cache` in the **customer** database (the same DB used for preview SQL). One row per node’s cached preview. No Parquet, no object storage, no per-node tables.
- **Payload**: JSONB (`row_data` = list of row dicts), `row_count` INTEGER. **Strict limit: at most 100 rows per cache entry**; preview results are truncated to 100 rows before storing.
- **Manager**: `api/services/adaptive_cache.py` — `AdaptiveCacheManager` / `AdaptiveCacheManagerV2`.
- **No in-memory cache**: All cached data is stored in this table (DB-only checkpoint cache).

### 4.2 When cache is used

- When the user asks for a **preview** of a node (e.g. filter or join), the Django view:
  1. Builds the **execution path** from that node back to sources (or to a **nearest cached ancestor**).
  2. If a **nearest cached ancestor** exists and is still valid (same node/upstream version hashes, not expired), it **reads from cache** for that ancestor and then runs **only the path from cache to target** (SQL for the rest).
  3. After computing the target node’s result, it may **write** that result to the cache if the node is considered “high cost” (see below).

So cache **shortens** how much of the pipeline is re-executed for preview, and **stores** results of expensive nodes for reuse.

### 4.3 Which nodes get cached

- **Source**: Cached so repeated previews can reuse the same extracted/filtered source data.
- **Join, aggregate, compute** (with non-trivial code), **window, sort**: Cached when considered high cost.
- **Filter**: Cached when it’s “large” (e.g. row reduction above threshold, or pushdown candidate, or high fan-out).
- **Projection**: Usually not cached unless it has calculated columns (medium cost).

Details are in `AdaptiveCacheManager.should_cache()` in `api/services/adaptive_cache.py`. Only one layer is used: `CacheLayer.CHECKPOINT` (DB table).

### 4.4 Cache key, expiry, and indexes

- Rows in `preview_node_cache` are keyed by `(pipeline_id, node_id)` and version hashes (`node_version_hash`, `upstream_version_hash`).
- Rows have **created_at** and **expires_at** (default TTL 15 minutes). Expired rows are ignored on read.
- **Required indexes**: `(pipeline_id, node_id)` for lookup; `(expires_at)` for TTL cleanup.

### 4.5 When cache is invalidated

- **Explicit invalidation** (downstream caches deleted):
  - **Node delete**: `api/views/node_management.py` calls `invalidate_downstream_caches(node_id, nodes, edges, cache_manager, pipeline_id)` so all cache entries for nodes downstream of the deleted node are removed.
  - **Node insert / edge change**: `api/views/node_addition.py` (and node_management where edges change) calls `invalidate_downstream_caches` so the new graph does not use stale cached results for affected nodes.
- **Implicit invalidation** (no delete; lookup fails):
  - **Config or upstream change**: When the user edits a node’s config or the upstream graph changes, `node_version_hash` and/or `upstream_version_hash` change. The next preview lookup uses the new hashes, so the old cache row is not returned (it is effectively invalid).
- **TTL**: Rows have `created_at` and `expires_at` (default 15 minutes). Rows with `expires_at <= CURRENT_TIMESTAMP` are ignored on read. **Background cleanup**: call `cache_manager.delete_expired_cache_rows()` from a periodic task (e.g. Celery beat) or on-demand to delete expired rows; index on `expires_at` is used for fast cleanup.

So: **node cache = single-table, JSONB, ≤100 rows per entry, preview-only, DB-only, TTL-based, and invalidated on graph changes (explicit) or config/upstream changes (implicit via version hashes).**

---

## 5. How Destination Tables Are Created

Destination tables are created and filled by **loaders** in the Migration Service: **PostgresLoader** or **HanaLoader**, depending on `db_type` in the destination config.

### 5.1 When is a table created?

- The destination node has a **load mode** (e.g. "insert", "drop_and_reload").
- **create_if_not_exists**: True when load mode is `insert` or `drop_and_reload`.
- **drop_and_reload**: True only when load mode is `drop_and_reload` (then the loader drops the table if it exists, then creates and inserts).

So:
- **Insert**: Create table if it doesn’t exist; then insert rows (existing table: append).
- **Drop and reload**: Drop table if exists → create table → insert all rows.

### 5.2 Where do column names come from?

- The data arriving at the destination is a **list of dicts** (one dict per row). **Keys** of the first row (and any other keys seen in the data) define the **column names**.
- Before loading, the orchestrator may **remap** row keys using `node_output_metadata` for the **direct upstream** node: technical/db names → **business (display) names**. So the loader often sees **business names** as keys.
- The loader:
  1. Infers the column list from the **keys** of the data (e.g. `_all_columns_from_data(data)`).
  2. Optionally **normalizes** names (e.g. for PostgreSQL safe identifiers).
  3. If **create_if_not_exists** and the table doesn’t exist (or was dropped): it infers **types** from the Python values and runs **CREATE TABLE** with those column names.
  4. Inserts rows using those same column names.

So: **destination table and column names** ultimately come from the **row dict keys** after any remap. We agreed that when the table is created, it should use **business names**; the remap step is what makes the keys business names before the loader sees them.

### 5.3 PostgreSQL loader (short)

- **File**: `services/migration_service/postgres_loader.py`.
- **Connection**: From `destination_config` (host, port, database, user, password).
- **Table name**: From node config `tableName`; optional `schema`.
- If **drop_and_reload**: `_drop_table` then create.
- If **create_if_not_exists** and table missing (or schema mismatch): `_create_table_if_not_exists(...)` using inferred columns and types from the data.
- **Insert**: Prefer **COPY** (bulk) for speed; fallback to **executemany** if COPY fails.

So: **destination tables are created from the same column names that are in the (remapped) row dicts — i.e. business names when remap is applied.**

---

## 6. End-to-End Summary (for a new developer)

1. **User clicks Execute**  
   → Frontend calls Django API to start migration.

2. **Django** creates a `MigrationJob`, builds config (sources, destinations, and for each destination’s upstream, `node_output_metadata` from the SQL compiler), and enqueues **Celery** `execute_migration_task(job_id)`.

3. **Celery** task POSTs to **FastAPI** `POST /execute` with job_id, canvas_id, nodes, edges, config. Django does **not** run the pipeline.

4. **FastAPI** stores the job and runs **Orchestrator.execute_pipeline** in a background task. The orchestrator:
   - Builds **execution levels** (topological).
   - For each level, runs all nodes in that level **in parallel**.
   - **Source** nodes: call Extraction Service, put rows in `results`.
   - **Transform** nodes (filter, projection, join, compute): take data from `results` (one or two upstreams), do in-memory join or pass-through, put result in `results`.
   - **Destination** nodes: take upstream data from `results`, **remap** to business names if metadata exists, then call **PostgresLoader** or **HanaLoader** to create table (if needed) and insert rows.

5. **Node cache** is **not** used in this path. It is used only in the **preview** path in Django (SQL compiler + `AdaptiveCacheManager`), to avoid re-running the whole pipeline when the user previews a node multiple times.

6. **Destination tables** get their **column names** from the **keys of the row dicts** that the loader receives. Those keys are business names when the orchestrator has applied the **node_output_metadata** remap. The loader infers types, runs CREATE TABLE if needed, then INSERT (or COPY).

If you follow this flow, you can trace from "Execute" to "table created with business-named columns" and see that **node cache** only affects **preview**, not the migration run.
