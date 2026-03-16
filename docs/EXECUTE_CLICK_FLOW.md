# Execute button click – which files are called

When you click **Execute** on the canvas, the flow goes through these files in order.

## Pipeline not running after 202? (Fixed)

**Root causes addressed:**
1. **BackgroundTasks not running** – FastAPI `BackgroundTasks` can fail to run in some uvicorn/worker setups. Switched to `asyncio.create_task()` so the pipeline runs immediately in the event loop.
2. **"Job already registered" blocking** – Previously returned early when any job with that `job_id` existed in Redis. Now only blocks when status is `RUNNING`; `PENDING`/`COMPLETED`/`FAILED` jobs allow (re)run so the pipeline actually executes.

---

## 1. Frontend (UI click → Django API)

| Order | File | What happens |
|-------|------|----------------|
| 1 | `frontend/src/components/Canvas/DataFlowCanvasChakra.tsx` | `handleExecute` (≈ line 3918) runs when the Execute button is clicked. |
| 2 | `frontend/src/lib/axios/api-client.ts` | `migrationApi.execute(canvasId, { ... })` (≈ line 112) sends **POST** to Django. |
| 3 | `frontend/src/constants/server-routes.ts` | Route: `migration.execute` → **`/api/migration-jobs/execute/`** (Django). |

---

## 2. Django (create job → Celery task → POST to migration service)

| Order | File | What happens |
|-------|------|----------------|
| 4 | `api/urls.py` | `migration-jobs` → `MigrationJobViewSet`; **POST** to `execute` action. |
| 5 | `api/views/migration_views.py` | `MigrationJobViewSet.execute` (≈ line 60): validates body, loads canvas/customer, builds config, creates `MigrationJob`, enqueues Celery task, returns 202 with `job_id`. |
| 6 | `api/utils/migration_config_builder.py` | `build_migration_config(canvas, customer, config)` – used by the execute view to build `source_configs` and `connection_config`. |
| 7 | `api/tasks/migration_tasks.py` | `execute_migration_task.delay(migration_job.id)` runs in Celery; task loads job/canvas, then **POST** to migration service **`http://localhost:8003/execute`** with `job_id`, `canvas_id`, `nodes`, `edges`, `config`. |

---

## 3. Migration service (FastAPI – execute endpoint → pipeline)

| Order | File | What happens |
|-------|------|----------------|
| 8 | `services/migration_service/main.py` | FastAPI app includes `migration_router`; route **POST /execute** is served. |
| 9 | `services/migration_service/routers/migration_routes.py` | **POST /execute** (≈ line 314): check “already running”, resolve plan (reuse from DB or build), register job in Redis, schedule **`execute_migration_pipeline`** via **BackgroundTasks**, return 202. |
| 10 | `services/migration_service/routers/migration_routes.py` | **`execute_migration_pipeline`** (async, ≈ line 85): deserializes plan if present, calls `execute_pipeline_pushdown`. |
| 11 | `services/migration_service/orchestrator/execute_pipeline_pushdown.py` | **`execute_pipeline_pushdown`**: runs phases (DB init, staging, levels, destination, cleanup). Uses planner for SQL when plan is built here (no plan reuse) or uses the passed-in plan when reused. |
| 12 | `services/migration_service/planner/execution_plan.py` | Used for plan hash, load/save/deserialize plan (e.g. `get_latest_plan`, `deserialize_plan`). |
| 13 | `services/migration_service/planner/sql_compiler.py` | Used when building a new plan (compile staging/join SQL, etc.). |

---

## Quick list (files only)

1. `frontend/src/components/Canvas/DataFlowCanvasChakra.tsx` – click handler  
2. `frontend/src/lib/axios/api-client.ts` – `migrationApi.execute`  
3. `frontend/src/constants/server-routes.ts` – URL constant  
4. `api/urls.py` – route to ViewSet  
5. `api/views/migration_views.py` – execute action (create job, enqueue task)  
6. `api/utils/migration_config_builder.py` – build config  
7. `api/tasks/migration_tasks.py` – Celery task → POST to migration service  
8. `services/migration_service/main.py` – mount router  
9. `services/migration_service/routers/migration_routes.py` – POST /execute + `execute_migration_pipeline`  
10. `services/migration_service/orchestrator/execute_pipeline_pushdown.py` – run pipeline  
11. `services/migration_service/planner/execution_plan.py` – plan hash/load/save  
12. `services/migration_service/planner/sql_compiler.py` – SQL when building plan  

---

## URLs

- **Django (frontend calls):** `POST /api/migration-jobs/execute/`  
- **Migration service (Django Celery task calls):** `POST http://localhost:8003/execute`
