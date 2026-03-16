# Execute Button Verification: Frontend → Backend

Verified flow for the Execute button (pipeline execution).

---

## 1. Frontend (Execute button)

**File:** `frontend/src/components/Canvas/DataFlowCanvasChakra.tsx`

| Step | What happens |
|------|----------------|
| Click | Execute button calls `handleExecute()`. |
| Pre-checks | Canvas must be saved (`canvasId`). Join nodes validated (left/right, conditions). Server-side validation via `POST /api/metadata/validate_pipeline/` (awaited). |
| Request | `migrationApi.execute(canvasId, { nodes, edges })` |
| API call | **POST** to `/api/migration-jobs/execute/` (from `ServerRoutes.migration.execute`). |
| Body | `{ canvas_id: canvasId, nodes: [...], edges: [...] }` (nodes/edges normalized with handles). |
| Auth | Same axios `api` instance (cookies / `withCredentials`). |

**Success:** Toast "Migration triggered" + job ID; view switches to `monitor`; WebSocket subscribe for that job.

**Failure:** Toast "Migration not triggered" + error message from `error.response?.data?.error` or `error.message`.

---

## 2. API client

**File:** `frontend/src/lib/axios/api-client.ts`

- `migrationApi.execute(canvasId, config)` → `api.post(ServerRoutes.migration.execute, { canvas_id: canvasId, ...config })`.
- So body = `{ canvas_id, nodes, edges }`.
- Base URL from `API_BASE_URL` (e.g. `http://localhost:8000`). Full URL: `{API_BASE_URL}/api/migration-jobs/execute/`.

---

## 3. Backend route

**File:** `api/urls.py`

- Router: `router.register(r'migration-jobs', MigrationJobViewSet, basename='migration-job')`.
- Main app: `path('api/', include('api.urls'))`.
- **Result:** **POST** `/api/migration-jobs/execute/` → `MigrationJobViewSet.execute` (custom action).

---

## 4. Backend view

**File:** `api/views/migration_views.py` → `MigrationJobViewSet.execute`

| Step | What happens |
|------|----------------|
| Input | `request.data` = `{ canvas_id, nodes?, edges?, config? }`. |
| Validation | `MigrationJobCreateSerializer`: requires `canvas_id` (int), optional `config` (JSON). Extra keys (`nodes`, `edges`) are allowed and ignored. |
| Load canvas | `Canvas.objects.get(id=canvas_id, is_active=True)`. |
| Create job | `MigrationJob` created with `job_id` (UUID), `canvas`, `customer`, `status='pending'`, `config`. |
| Trigger run | `execute_migration_task.delay(migration_job.id)`. If broker (Redis) fails: fallback to `execute_migration_task.apply(args=[migration_job.id])` in a background thread. |
| Response | **202 Accepted** + `{ "job_id": "<uuid>", "status": "pending", "message": "Migration job started" }`. |

**Important:** Execution uses **saved** canvas state: `canvas.get_nodes()` and `canvas.get_edges()` in the Celery task. Request body `nodes`/`edges` are not used for execution (they are optional for future use or debugging).

---

## 5. Contract summary

| Item | Frontend | Backend | Status |
|------|----------|---------|--------|
| URL | `POST /api/migration-jobs/execute/` | Same | OK |
| Method | POST | POST | OK |
| Body | `canvas_id`, `nodes`, `edges` | Expects `canvas_id` (required), `config` (optional); extra keys allowed | OK |
| Response | Expects `response.data.job_id` | 202 + `{ job_id, status, message }` | OK |
| Auth | Cookie / credentials | `IsAuthenticated`, `JWTCookieAuthentication` | OK |

---

## 6. How to confirm it’s working

1. **Success path**
   - Click Execute (after saving canvas and passing validation).
   - Green toast: "Migration triggered" with Job ID.
   - View switches to monitor.
   - Backend logs: job created, task enqueued or run in thread; no 500.

2. **Failure path**
   - Red toast: "Migration not triggered" with message (e.g. Redis error, canvas not found).
   - Backend returns 4xx/5xx; message in `response.data.error` or exception message.

3. **Network**
   - In DevTools → Network, filter for `migration-jobs/execute/`.
   - You should see one **POST** with status **202** on success, or 4xx/5xx on failure.

---

## 7. Conclusion

Execute button flow from frontend to backend is **correct**:

- URL, method, body, and response match.
- Backend uses saved canvas for execution; request nodes/edges are not required.
- Success and error feedback are shown via toasts and optional WebSocket updates.
