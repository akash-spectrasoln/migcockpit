# Reorganize API Directory - Separate React API from Django Templates

## Current Problems

1. **api/views.py** - Massive file (13,000+ lines) with many API views mixed together
2. **Mixed concerns** - React frontend API endpoints (JSON) and Django template views (HTML) are in the same app
3. **Scattered files** - Utility files like `compute_execution.py`, `calculated_column_evaluator.py`, `filters.py` at root level
4. **Poor separation** - React API endpoints and Django template rendering are not clearly separated
5. **Hard to maintain** - Large monolithic `views.py` file makes it difficult to find and modify specific endpoints

## User Requirement

**IMPORTANT**: Keep Django template views (`api/frondendviews.py` and `api/templates/`) **unchanged**. Only separate the React frontend API endpoints into a new app.

## Proposed Architecture

### New Structure

```
datamigration-migcockpit/
├── api/                          # Django template views (UNCHANGED)
│   ├── frondendviews.py          # Template-rendering views (KEEP AS-IS)
│   ├── templates/                # HTML templates (KEEP AS-IS)
│   ├── urls.py                   # Will include both template URLs and React API URLs
│   └── ... (other existing files)
│
├── react_api/                    # NEW - React frontend API endpoints (JSON only)
│   ├── __init__.py
│   ├── apps.py
│   ├── urls.py                   # React API URLs
│   ├── views/                    # Organized React API views
│   │   ├── __init__.py           # Export all views for backward compatibility
│   │   ├── auth.py               # Authentication APIs (LoginView, LogoutView, RefreshTokenView)
│   │   ├── sources.py            # Source APIs (CustomerSourcesView, SourceEditView, etc.)
│   │   ├── destinations.py       # Destination APIs (CustomerDestinationsView, etc.)
│   │   ├── pipeline.py          # Pipeline execution APIs (PipelineQueryExecutionView, FilterExecutionView, JoinExecutionView)
│   │   ├── compute.py            # Compute node APIs (ComputeNodeExecutionView, ComputeNodeCompileView)
│   │   ├── expression.py         # Expression validation APIs (ValidateExpressionView, TestExpressionView)
│   │   └── tables.py             # Table management APIs (if used by React)
│   ├── utils/                    # Utility modules for React API
│   │   ├── __init__.py
│   │   ├── compute_execution.py  # Moved from api/compute_execution.py
│   │   ├── calculated_column_evaluator.py  # Moved from api/calculated_column_evaluator.py
│   │   └── filters.py            # Moved from api/filters.py
│   └── services/                 # Business logic services (if needed)
│
└── api/                          # Existing API app (Django templates)
    ├── views/                    # Existing organized views (canvas_views, migration_views, etc.)
    ├── serializers/              # DRF serializers
    ├── models/                   # Database models
    ├── services/                 # Business logic services
    └── ... (other existing files)
```

## React Frontend API Endpoints (to move to react_api)

Based on `frontend/src/constants/server-routes.ts` and `frontend/src/lib/axios/api-client.ts`:

### Authentication APIs
- `LoginView` (`/api/api-login/`)
- `LogoutView` (`/api/api-logout/`)
- `RefreshTokenView` (`/api/api-refresh/`)

### Source APIs
- `CustomerSourcesView` (`/api/api-customer/sources/`)
- `SourceEditView` (`/api/api-customer/sources/<id>/edit/`)
- `SourceDeleteView` (`/api/api-customer/sources/<id>/delete/`)
- `SourceTablesView` (`/api/api-customer/sources/<id>/tables/`)
- `SourceTableSelectionView` (`/api/api-customer/sources/<id>/selected-tables/`)
- `SourceTableDataView` (`/api/api-customer/sources/<id>/table-data/`)
- `SourceColumnsView` (`/api/api-customer/sources/<id>/columns/`)
- `SourceConnectionCreateView` (`/api/sources-connection/`)
- `SourceConnectionCreateWithValidationView` (`/api/sources-connection-validate/`)
- `SourceAttributesView` (`/api/source-attributes/`)
- `FilterExecutionView` (`/api/api-customer/sources/<id>/filter/`)
- `JoinExecutionView` (`/api/api-customer/sources/<id>/join/`)

### Destination APIs
- `CustomerDestinationsView` (`/api/api-customer/destinations/`)
- `DestinationEditView` (`/api/api-customer/destinations/<id>/edit/`)
- `DestinationDeleteView` (`/api/api-customer/destinations/<id>/delete/`)
- `DestinationConnectionCreateView` (`/api/destinations-connection/`)

### Pipeline APIs
- `PipelineQueryExecutionView` (`/api/pipeline/execute/`)

### Expression APIs
- `ValidateExpressionView` (`/api/validate-expression/`)
- `TestExpressionView` (`/api/test-expression/`)

### Compute Node APIs
- `ComputeNodeExecutionView` (`/api/compute/execute/`)
- `ComputeNodeCompileView` (`/api/compute/compile/`)

### Node Cache APIs (already in api/views/node_cache_views.py)
- `NodeCacheView` (`/api/node-cache/<canvas_id>/<node_id>/`)
- `NodeCacheStatsView` (`/api/node-cache/stats/`)
- `NodeCacheCleanupView` (`/api/node-cache/cleanup/`)

### ViewSets (already organized in api/views/)
- `CanvasViewSet` (`/api/canvas/`) - Keep in api/views/canvas_views.py
- `MigrationJobViewSet` (`/api/migration-jobs/`) - Keep in api/views/migration_views.py
- `MetadataViewSet` (`/api/metadata/`) - Keep in api/views/metadata_views.py
- `ProjectViewSet` (`/api/projects/`) - Keep in api/views/project_views.py

## Implementation Steps

### Phase 1: Create React API App

1. **Create Django app `react_api`**
   ```bash
   python manage.py startapp react_api
   ```

2. **Add to INSTALLED_APPS**
   - Add `'react_api'` to `INSTALLED_APPS` in `datamigrationapi/settings.py`

3. **Create directory structure**
   - Create `react_api/views/` directory
   - Create `react_api/utils/` directory
   - Create `react_api/services/` directory (if needed)

### Phase 2: Extract React API Views from api/views.py

1. **Create react_api/views/auth.py**
   - Move `LoginView`, `LogoutView`, `RefreshTokenView` from `api/views.py`
   - Update imports to use shared utilities from `api` app

2. **Create react_api/views/sources.py**
   - Move source-related views:
     - `CustomerSourcesView`
     - `SourceEditView`
     - `SourceDeleteView`
     - `SourceTablesView`
     - `SourceTableSelectionView`
     - `SourceTableDataView`
     - `SourceColumnsView`
     - `SourceConnectionCreateView`
     - `SourceConnectionCreateWithValidationView`
     - `SourceAttributesView`
     - `FilterExecutionView`
     - `JoinExecutionView`
   - Import shared utilities from `api` app

3. **Create react_api/views/destinations.py**
   - Move destination-related views:
     - `CustomerDestinationsView`
     - `DestinationEditView`
     - `DestinationDeleteView`
     - `DestinationConnectionCreateView`

4. **Create react_api/views/pipeline.py**
   - Move `PipelineQueryExecutionView` from `api/views.py`
   - This is a large view, keep it in one file for now

5. **Create react_api/views/compute.py**
   - Move `ComputeNodeExecutionView` and `ComputeNodeCompileView` from `api/compute_execution.py`

6. **Create react_api/views/expression.py**
   - Move `ValidateExpressionView` from `api/views/expression_validation.py`
   - Move `TestExpressionView` from `api/views/expression_testing.py`
   - Or keep them in their existing files and import them

7. **Create react_api/views/__init__.py**
   - Export all views for backward compatibility
   - Maintain existing import paths: `from react_api.views import X`

### Phase 3: Move Utility Modules

1. **Move compute_execution.py**
   - `api/compute_execution.py` → `react_api/utils/compute_execution.py`
   - Update imports in `react_api/views/compute.py`

2. **Move calculated_column_evaluator.py**
   - `api/calculated_column_evaluator.py` → `react_api/utils/calculated_column_evaluator.py`
   - Update imports in `react_api/views/pipeline.py`

3. **Move filters.py**
   - `api/filters.py` → `react_api/utils/filters.py`
   - Update imports where used

### Phase 4: Create React API URLs

1. **Create react_api/urls.py**
   - Define all React API URL patterns
   - Import views from `react_api.views` modules
   - Use same URL paths as before (e.g., `/api/api-login/`)

2. **Update datamigrationapi/urls.py**
   - Include `react_api.urls` before `api.urls`
   - This ensures React API endpoints are available at `/api/...`

3. **Update api/urls.py**
   - Remove React API URL patterns (moved to `react_api/urls.py`)
   - Keep Django template URL patterns (`frontend_urlpatterns`)
   - Keep ViewSet URLs (canvas, migration, metadata, projects)

### Phase 5: Update Imports

1. **Update react_api/views/__init__.py**
   - Export all views for easy importing
   - Maintain backward compatibility

2. **Update files that import from api.views**
   - Update imports to use `react_api.views` for React API endpoints
   - Keep imports from `api.views` for ViewSets and shared utilities

3. **Update shared utilities**
   - Ensure utility functions in `api` app can be imported by `react_api`
   - Functions like `ensure_user_has_customer`, `generate_encryption_key`, etc.

### Phase 6: Testing and Cleanup

1. **Test all React API endpoints**
   - Verify all endpoints work correctly
   - Check authentication flows
   - Test pipeline execution
   - Test source/destination operations

2. **Cleanup**
   - Remove moved views from `api/views.py`
   - Delete `api/compute_execution.py` (moved to `react_api/utils/`)
   - Delete `api/calculated_column_evaluator.py` (moved to `react_api/utils/`)
   - Delete `api/filters.py` (moved to `react_api/utils/`)
   - Update documentation

## Files to Create

### New Files
- `react_api/__init__.py`
- `react_api/apps.py`
- `react_api/urls.py`
- `react_api/views/__init__.py`
- `react_api/views/auth.py`
- `react_api/views/sources.py`
- `react_api/views/destinations.py`
- `react_api/views/pipeline.py`
- `react_api/views/compute.py`
- `react_api/views/expression.py`
- `react_api/utils/__init__.py`
- `react_api/utils/compute_execution.py` (from `api/compute_execution.py`)
- `react_api/utils/calculated_column_evaluator.py` (from `api/calculated_column_evaluator.py`)
- `react_api/utils/filters.py` (from `api/filters.py`)

### Files to Modify
- `datamigrationapi/settings.py` - Add `'react_api'` to INSTALLED_APPS
- `datamigrationapi/urls.py` - Include `react_api.urls`
- `api/urls.py` - Remove React API URL patterns, keep template URLs
- `api/views.py` - Remove React API views (extract to react_api)
- Files importing from `api.views` - Update to use `react_api.views` where appropriate

### Files to Delete (after migration)
- `api/compute_execution.py` (moved to `react_api/utils/`)
- `api/calculated_column_evaluator.py` (moved to `react_api/utils/`)
- `api/filters.py` (moved to `react_api/utils/`)

### Files to Keep Unchanged
- `api/frondendviews.py` - Django template views (KEEP AS-IS)
- `api/templates/` - HTML templates (KEEP AS-IS)
- `api/views/canvas_views.py` - ViewSet (KEEP)
- `api/views/migration_views.py` - ViewSet (KEEP)
- `api/views/metadata_views.py` - ViewSet (KEEP)
- `api/views/project_views.py` - ViewSet (KEEP)
- `api/views/node_cache_views.py` - Can keep or move to react_api

## Benefits

1. **Clear Separation**: React API endpoints (JSON) and Django template views (HTML) are completely separated
2. **Better Organization**: React API views organized by domain (auth, sources, destinations, pipeline)
3. **Easier Maintenance**: Smaller, focused files instead of one massive file
4. **Scalability**: Easy to add new React API endpoints without cluttering existing files
5. **Better Testing**: Each module can be tested independently
6. **No Breaking Changes**: Django template views remain untouched
7. **Backward Compatibility**: Can maintain import compatibility through `__init__.py` exports

## Migration Strategy

- **Backward Compatibility**: Use `react_api/views/__init__.py` to maintain existing imports where possible
- **Gradual Migration**: Can be done incrementally, testing after each phase
- **No Breaking Changes**: All existing URLs continue to work, just routed from different app
- **Django Templates Unchanged**: Template views remain in `api` app, no changes needed

## URL Routing

```
/api/api-login/              → react_api.views.auth.LoginView
/api/api-customer/sources/   → react_api.views.sources.CustomerSourcesView
/api/pipeline/execute/       → react_api.views.pipeline.PipelineQueryExecutionView
/api/compute/execute/        → react_api.views.compute.ComputeNodeExecutionView
/api/canvas/                 → api.views.canvas_views.CanvasViewSet (ViewSet)
/api/migration-jobs/         → api.views.migration_views.MigrationJobViewSet (ViewSet)
/api/login/                  → api.frondendviews.login_page (Django template)
/api/customer/sources/       → api.frondendviews.customer_sources (Django template)
```
