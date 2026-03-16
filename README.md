# Data Migration Cockpit

A visual ETL and data migration platform for designing, validating, and running data pipelines. Build pipelines on a canvas (sources → transforms → destinations), then execute them with SQL pushdown and optional background jobs.

---

## Features

- **Visual pipeline design** — Drag-and-drop canvas with nodes for sources, projections, filters, joins, aggregates, computed/calculated columns, and destinations
- **Schema propagation** — Column include/exclude and validation flow from projection nodes downstream; per-column errors and auto-healing
- **Save workflow** — All canvas changes (add/delete/edit nodes and config) stay frontend-only until you click **Save Pipeline**; refresh loads the last saved pipeline (Tableau/Power BI–style)
- **Multiple sources & destinations** — Connect to SQL Server, PostgreSQL, and other sources; write to customer DB or remote targets
- **Validation & execution** — Validate pipeline structure and metadata, then run migrations with progress tracking
- **Background jobs** — Celery workers for long-running migrations; optional WebSocket for real-time progress

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend API** | Django 4.x, Django REST Framework, JWT auth |
| **Frontend** | React 18, TypeScript, Vite, Chakra UI, React Flow, Zustand, React Query |
| **Tasks** | Celery, Redis |
| **Database** | PostgreSQL (main app + optional customer DB for migration targets) |
| **Services** | FastAPI (extraction, migration orchestration, WebSocket) |

---

## Project Structure

```
datamigration-migcockpit/
├── api/                    # Django app: REST API, canvas, sources, pipeline, auth
├── api_admin/               # Django admin app
├── datamigrationapi/        # Django project (settings, urls, celery)
├── frontend/                # React app (Vite, Chakra, React Flow)
│   └── src/
│       ├── components/     # UI and Canvas components
│       ├── pages/          # Login, Canvas, Dashboard, Jobs
│       ├── store/          # Zustand (auth, canvas)
│       ├── pipeline-engine/ # Schema propagation, validation, compilation
│       └── services/       # API client
├── services/                # Standalone FastAPI services
│   ├── migration_service/  # ETL orchestration, SQL pushdown
│   ├── extraction_service/ # Data extraction from sources
│   └── websocket_server/   # Real-time progress
├── docs/                   # Architecture, startup, guides
├── scripts/                # Start/stop all services (Windows + Linux/Mac)
└── tests/                  # Pytest tests
```

---

## Prerequisites

- **Python 3.9+**
- **Node.js 16+** and npm
- **PostgreSQL** (e.g. DB `datamigrate`, port 5433)
- **Redis** (port 6379) for Celery

---

## Quick Start

### 1. Clone and install

```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

### 2. Configure environment

Create a `.env` in the project root (see `.env.example` if present). Typical options:

- `DATABASE_URL` or Django `DATABASES` settings for PostgreSQL
- `CELERY_BROKER_URL=redis://localhost:6379/0`
- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` for Django

### 3. Database and superuser

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 4. Start services

**Windows (batch):**

```batch
scripts\start_all_services.bat
```

**Linux/Mac:**

```bash
chmod +x scripts/start_services.sh
./scripts/start_services.sh
```

Or start manually:

1. Redis: `redis-server`
2. Django: `python manage.py runserver 8000`
3. Celery: `celery -A datamigrationapi worker --loglevel=info`
4. Frontend: `cd frontend && npm run dev`
5. (Optional) FastAPI services: extraction (8001), migration (8003), WebSocket (8004) — see `docs/README_STARTUP.md`

### 5. Open the app

- **Frontend:** http://localhost:5173 (Vite) or http://localhost:3000 (if configured)
- **Django Admin:** http://localhost:8000/admin

Log in with the superuser account, create or open a project, then open a canvas to design pipelines.

---

## Services and Ports

| Service | Port | Description |
|---------|------|-------------|
| Django API | 8000 | REST API, auth, canvas CRUD, save-configuration |
| React (Vite) | 5173 / 3000 | UI and canvas |
| Extraction Service | 8001 | FastAPI – fetch tables/columns from sources |
| Migration Service | 8003 | FastAPI – orchestration, execution plans |
| WebSocket Server | 8004 | Real-time execution progress |
| Redis | 6379 | Celery broker |
| PostgreSQL | 5433 | Main DB (configurable) |

---

## Key Concepts

- **Canvas** — One pipeline per canvas; nodes (source, projection, filter, join, aggregate, compute, calculated column, destination) and edges define the DAG.
- **Save Pipeline** — The only action that persists the full graph (nodes, edges, config) to the backend. All other edits (add/delete/insert node, change config) are local until you click **Save Pipeline**; a refresh discards unsaved changes and reloads the last saved pipeline.
- **Projection columns** — Include/exclude is defined at projection nodes; added/removed columns propagate to the next node(s) and downstream, with validation and per-column errors.

---

## Documentation

- **Startup and run:** `docs/README_STARTUP.md`
- **Docs index:** `docs/README.md`
- **Application flow:** `docs/APPLICATION_FLOW.md`
- **Frontend:** `frontend/README.md`
- **Services layout:** `services/README.md`

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/start_all_services.bat` | Start all services (Windows) |
| `scripts/stop_all_services.bat` | Stop all services (Windows) |
| `scripts/start_services.sh` | Start all services (Linux/Mac) |

---

## License

Proprietary / internal use unless otherwise stated.
