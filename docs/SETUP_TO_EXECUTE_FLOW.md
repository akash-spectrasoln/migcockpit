# Setup to Execute the Data Migration Flow

Use this checklist to get the Data Migration Cockpit running so you can design and **execute** pipelines.

---

## Executing the pipeline on the canvas (Execute button)

When you click **Execute** on the canvas, the app runs a **migration job**: it sends the pipeline (nodes/edges) to Django, which creates a job and hands it to Celery; Celery calls the **Migration Orchestrator**, which coordinates extraction and loading (and uses the **Extraction Service** and **WebSocket** for progress).

### What must be running for Execute to work

| Service | Port | Why |
|--------|------|-----|
| **Django API** | 8000 | Receives Execute, creates job, enqueues Celery task |
| **Celery worker** | - | Runs the migration task and calls the Orchestrator |
| **Redis** | 6379 | Celery broker (must be running) |
| **Migration Orchestrator** | 8003 | Runs the migration; called by Celery |
| **Extraction Service** | 8001 | Used by Orchestrator for data extraction |
| **WebSocket Server** | 8004 | Live progress in UI (optional for job to complete, but UI expects it) |
| **React Frontend** | 3000 | To click Execute and see status |
| **PostgreSQL** | 5433 | Canvas, sources, destinations, migration jobs |

If any of these are down, **Execute** can fail or hang (e.g. no Celery → job stays pending; no Orchestrator → task fails).

### What must be configured on the canvas

- **Canvas is saved** – Execute is disabled until the canvas is saved (you get a “Please save the canvas first” toast otherwise).
- **At least one Source node** – with a source connection and table/schema chosen.
- **At least one Destination node** – with a destination connection and schema/table chosen.
- **Join nodes** (if any) – must have both left and right inputs connected and join conditions set; otherwise validation blocks Execute.
- **Pipeline connected** – Source → transforms → Destination as intended.

### Flow when you click Execute

1. Frontend calls `POST /api/migration-jobs/execute/` with `canvas_id`, `nodes`, `edges`.
2. Django creates a `MigrationJob` record, enqueues **Celery** task `execute_migration_task`.
3. Django returns `job_id` (202 Accepted); UI switches to monitor view and subscribes to **WebSocket** for that job.
4. **Celery** runs the task: it POSTs to **Migration Orchestrator** at `http://localhost:8003/execute` with the same canvas/nodes/edges.
5. **Orchestrator** runs the pipeline (extraction → transform → load), calling **Extraction Service** (8001) and pushing progress to **WebSocket** (8004).
6. UI shows progress via WebSocket; when the job completes, status updates in the UI.

### What is saved vs created on every execution

- **Saved (workflow)**  
  Only the **graph** is persisted: **nodes** and **edges** are stored in the canvas’s `configuration` (JSON) when you click **Save Pipeline**. We do **not** save “each level” or execution levels anywhere.

- **Created on every execution**  
  When you click **Execute**, the backend loads the **saved** canvas and sends its nodes/edges to the **Migration Orchestrator**. The orchestrator then:
  1. Calls `build_pipeline(nodes, edges)` and **computes** **execution levels** (waves) from the graph each time.
  2. Runs `execute_pipeline()` level by level (nodes in the same level run in parallel).

  So **execution levels are derived from the saved graph on every run**; they are not stored in the database.

- **How the trigger works**  
  1. You click **Execute** (canvas must be saved).  
  2. Frontend sends `POST /api/migration-jobs/execute/` with `canvas_id` (and optional `config`).  
  3. Django loads the **Canvas** by `canvas_id`, creates a **MigrationJob**, and enqueues a **Celery** task.  
  4. The **Celery** task loads the same canvas and gets **nodes** and **edges** from `canvas.configuration` (the saved workflow). It POSTs those to the **Migration Orchestrator** at `http://localhost:8003/execute`.  
  5. The orchestrator **builds** the pipeline (and thus **computes** execution levels from nodes/edges) and **runs** it level by level in parallel.

  So **Execute always runs the last saved workflow** (the graph in the canvas’s configuration). Any unsaved changes on the canvas are not used for execution.

### How the pipeline runs: node-by-node, parallel until join, then downstream

The canvas is a **DAG** (Directed Acyclic Graph): Source(s) → transforms (Filter, Projection, etc.) → Join (if any) → more transforms → Destination. When you click **Execute**, the system runs the graph like this:

1. **Execution order (dependency order)**  
   The orchestrator uses a **topological sort** on the graph: each node runs only after all its **upstream** nodes have finished. So:
   - **Source nodes** run first (they have no incoming edges).
   - Then **downstream nodes** run in order: e.g. Source → Filter → Projection → … → Destination.

2. **Parallel branches (e.g. multiple sources)**  
   If you have **parallel branches** — for example two Source nodes, or Source A → Filter A and Source B → Projection B — those branches have **no dependency on each other**. So:
   - **Conceptually**: all nodes that have “no pending dependencies” at a given moment can run **in parallel** (e.g. both sources at once, or both branches until they meet).
   - **In practice**: the orchestrator today uses topological order and may run nodes in a **sequential** order that still respects dependencies (e.g. Source1 then Source2, then downstream). True parallel execution of same-level nodes would run all “ready” nodes in parallel (e.g. with `asyncio.gather`) at each step.

3. **Join as synchronization point**  
   A **Join** node has two inputs (left and right). So:
   - **Both** upstream branches (left and right) must **finish** before the Join runs.
   - The Join then runs once (using left + right data and join conditions).
   - After the Join, execution continues **downstream** in dependency order: e.g. Join → Filter → Projection → Destination.


4. **After the join**  
   From the Join onward, the graph is a single chain (or DAG with possible splits). Each node runs one by one in topological order, using the output of its upstream node(s).

**Summary:**

- **Each node** runs exactly once, in **dependency order** (topological order).
- **Parallel branches** (e.g. multiple sources or two branches before a join) run **in parallel** by level (via `asyncio.gather`); the **Join** runs only after both inputs finish; after the Join, execution continues by level toward the **Destination**.

So: for **Execute on the canvas** to work end-to-end, start **all six app services** (Django, Celery, Extraction, Orchestrator, WebSocket, Frontend) plus **Redis** and **PostgreSQL**, and ensure the canvas is saved and source/destination (and joins, if any) are configured.

---

## 1. Prerequisites (install once)

| Requirement | Version | Check |
|-------------|---------|--------|
| **Python** | 3.8+ | `python --version` |
| **Node.js** | 16+ | `node --version` |
| **npm** | (with Node) | `npm --version` |
| **PostgreSQL** | (any recent) | Running, port **5433** (or set `DATABASE_PORT`) |
| **Redis** | (for Celery) | Running on port **6379** |

- **PostgreSQL**: Create database `datamigrate` and ensure the app can connect (user/password in step 2).
- **Redis**: Required for Celery (background tasks). Windows: [Redis for Windows](https://github.com/microsoftarchive/redis/releases). Start with `redis-server` if not installed as a service.

---

## 2. Database configuration

From project root: `migcockpit\datamigration-migcockpit\`

**Option A – Environment variables (recommended)**  
Create a `.env` in `datamigration-migcockpit` (same folder as `manage.py`):

```env
DATABASE_NAME=datamigrate
DATABASE_USER=postgres
DATABASE_PASSWORD=YOUR_POSTGRES_PASSWORD
DATABASE_HOST=localhost
DATABASE_PORT=5433
DATABASE_SCHEMA=GENERAL
```

**Option B – Defaults in code**  
In `datamigrationapi/settings.py`, the defaults are:

- Database: `datamigrate`
- User: `postgres`
- Password: `SecurePassword123!`
- Host: `localhost`
- Port: **5433**

Change the password (and port if needed) to match your PostgreSQL setup.

---

## 3. Create database and schema (first time only)

If the database does not exist yet:

```bash
# Connect to PostgreSQL (adjust user/port if needed)
psql -U postgres -h localhost -p 5433

# In psql:
CREATE DATABASE datamigrate;
\c datamigrate
CREATE SCHEMA IF NOT EXISTS "GENERAL";
\q
```

---

## 4. Project setup (first time only)

**Terminal 1 – from `datamigration-migcockpit`:**

```batch
cd path\to\migcockpit\datamigration-migcockpit

REM Python virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

**Important:** Run `python manage.py migrate` using the **same environment** (same `.env` or same `DATABASE_*` / `DATABASE_SCHEMA` env vars) as when you start the Django server. Otherwise the server may connect to a different database or schema where the `migration_job` table was never created.

**If you see "relation migration_job does not exist":**

1. From the same folder where you run `manage.py runserver`, run: `python manage.py migrate`.
2. Use the same env for both (e.g. same `.env` in that folder, or set `DATABASE_NAME`, `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_SCHEMA` the same).
3. If the table is still missing (e.g. server uses a different schema), create it in the **current** DB/schema with:  
   `python manage.py ensure_migration_job_tables`  
   (Run with the same env as the server so it creates the tables where the server looks.)
4. Restart the Django server after migrating or running the command.

**Terminal 2 – frontend:**

```batch
cd path\to\migcockpit\datamigration-migcockpit\frontend
npm install
```

---

## 5. Start services (to execute the flow)

You need **all** of these running to design pipelines and **execute** them:

| Service | Port | Needed for flow execution |
|---------|------|----------------------------|
| Django API | 8000 | Canvas, pipeline run, sources/destinations |
| React Frontend | 3000 | UI and canvas |
| Celery Worker | - | Background extraction/processing |
| Extraction Service | 8001 | Data extraction (e.g. chunked) |
| Migration Orchestrator | 8003 | Migration coordination |
| WebSocket Server | 8004 | Real-time updates |

**Option A – One script (recommended)**  
From `datamigration-migcockpit` (folder that contains `manage.py`):

```batch
cd path\to\migcockpit\datamigration-migcockpit
scripts\start_all_services.bat
```

**Option B – Legacy script from parent folder**  
From `migcockpit` (parent of `datamigration-migcockpit`):

```batch
cd path\to\migcockpit
scripts\start_services.bat
```

**Option C – Manual start**  
From `datamigration-migcockpit` open separate terminals and run:

```batch
REM 1. Django
python manage.py runserver 8000

REM 2. Celery (new terminal)
celery -A datamigrationapi worker --loglevel=info

REM 3. Extraction (new terminal)
cd services\extraction_service && python main.py

REM 4. Migration Orchestrator (new terminal)
cd services\migration_service && python main.py

REM 5. WebSocket (new terminal)
cd services\websocket_server && python main.py

REM 6. Frontend (new terminal)
cd frontend && npm run dev
```

---

## 6. Verify and run a flow

1. **Open app:** http://localhost:3000  
2. **Log in** with the superuser you created.  
3. **Dashboard:** Add at least one **source** and one **destination** (e.g. PostgreSQL).  
4. **Canvas:** Open or create a canvas, add a **Source** node, then **Projection** / **Filter** / **Destination** as needed.  
5. **Execute:** Use the Run/Execute action on the canvas; results and errors will show in the UI (and in Django/Celery/FastAPI logs if something fails).

---

## 7. Quick checklist

- [ ] Python 3.8+, Node 16+, PostgreSQL, Redis installed/running  
- [ ] `.env` or `settings.py` database settings correct (port 5433 unless you changed it)  
- [ ] Database `datamigrate` and schema `GENERAL` created  
- [ ] `pip install -r requirements.txt` and `python manage.py migrate`  
- [ ] `python manage.py createsuperuser`  
- [ ] `cd frontend && npm install`  
- [ ] All 6 services started (Django, Celery, Extraction, Orchestrator, WebSocket, Frontend)  
- [ ] At least one source and one destination configured  
- [ ] Open http://localhost:3000, log in, design pipeline, then execute

---

## Troubleshooting

- **Port in use:** Change port in the start command or stop the process using that port (`netstat -ano | findstr :8000` then `taskkill /PID <id> /F`).  
- **PostgreSQL connection failed:** Check password, port (5433), and that PostgreSQL is running.  
- **Redis/Celery:** Ensure Redis is running on 6379; Celery must start without errors.  
- **Frontend blank/API errors:** Ensure Django is on 8000 and CORS is enabled; use browser dev tools Network tab to see which request fails.

For more detail: `docs/README_STARTUP.md`, `docs/DATABASE_SETUP.md`, `docs/QUICK_START.md`.
