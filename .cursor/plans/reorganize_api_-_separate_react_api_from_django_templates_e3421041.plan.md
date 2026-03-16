# Reorganize API Directory - Separate React API from Django Templates

## Current Structure Analysis

Based on user clarification:

### Files in `api/` directory:

**Django Template Views (KEEP in api/):**
- `frondendviews.py` - Django template rendering views
- `templates/` - HTML templates directory
- `urls.py` - Contains template URLs (frontend_urlpatterns) - will be cleaned up

**React Frontend API (MOVE to react_api/):**
- `views.py` - Large file (13,000+ lines) with React API endpoints
- `authentications.py` - Authentication logic (used by React API)
- `compute_execution.py` - Compute node execution
- `calculated_column_evaluator.py` - Calculated column evaluator
- `filters.py` - Filter utilities

**Shared Resources (KEEP in api/):**
- `models/` - Database models (shared by both)
- `serializers/` - DRF serializers (shared by both)
- `migrations/` - Database migrations (shared by both)
- `admin.py` - Django admin (shared by both)
- `apps.py` - Django app config (shared by both)
- `management/` - Management commands (shared by both)
- `services/` - Business logic services (shared by both)
- `tasks/` - Celery tasks (shared by both)
- `utilts.py` - Utilities (if shared, keep in api/)

## Proposed Architecture

### New Structure

```
datamigration-migcockpit/
├── api/                          # Django template views + shared resources
│   ├── frondendviews.py          # Template-rendering views (KEEP AS-IS)
│   ├── templates/                # HTML templates (KEEP AS-IS)
│   ├── urls.py                   # Template URLs only (clean up React API URLs)
│   ├── models/                   # Database models (KEEP - shared)
│   ├── serializers/              # DRF serializers (KEEP - shared)
│   ├── migrations/               # Database migrations (KEEP - shared)
│   ├── admin.py                  # Django admin (KEEP - shared)
│   ├── apps.py                   # Django app config (KEEP - shared)
│   ├── management/               # Management commands (KEEP - shared)
│   ├── services/                 # Business logic services (KEEP - shared)
│   ├── tasks/                    # Celery tasks (KEEP - shared)
│   ├── views/                    # Existing organized ViewSets (KEEP)
│   │   ├── canvas_views.py       # CanvasViewSet
│   │   ├── migration_views.py    # MigrationJobViewSet
│   │   ├── metadata_views.py    # MetadataViewSet
│   │   ├── project_views.py      # ProjectViewSet
│   │   └── node_cache_views.py   # NodeCacheView
│   └── utilts.py                 # Shared utilities (KEEP if shared)
│
├── react_api/                    # NEW - React frontend API endpoints (JSON only)
│   ├── __init__.py
│   ├── apps.py
│   ├── urls.py                   # React API URLs
│   ├── views/                    # Organized React API views
│   │   ├── __init__.py           # Export all views
│   │   ├── auth.py               # Authentication APIs (from views.py)
│   │   ├── sources.py            # Source APIs (from views.py)
│   │   ├── destinations.py       # Destination APIs (from views.py)
│   │   ├── pipeline.py          # Pipeline execution APIs (from views.py)
│   │   ├── compute.py            # Compute node APIs (from compute_execution.py)
│   │   └── expression.py         # Expression validation APIs
│   ├── utils/                    # Utility modules for React API
│   │   ├── __init__.py
│   │   ├── compute_execution.py  # Moved from api/compute_execution.py
│   │   ├── calculated_column_evaluator.py  # Moved from api/
│   │   └── filters.py            # Moved from api/filters.py
│   └── authentications.py         # Moved from api/authentications.py (if React-specific)
```

## React Frontend API Endpoints (to extract from api/views.py)

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
- `ValidateExpressionView` (`/api/validate-expression/`) - from api/views/expression_validation.py
- `TestExpressionView` (`/api/test-expression/`) - from api/views/expression_testing.py

### Compute Node APIs
- `ComputeNodeExecutionView` (`/api/compute/execute/`) - from api/compute_execution.py
- `ComputeNodeCompileView` (`/api/compute/compile/`) - from api/compute_execution.py

### Other APIs (from views.py)
- `SqlConnectionView` (`/api/fetch/`)
- `SourcesListView` (`/api/sources/`)
- `SourceFieldsView` (`/api/sources/<id>/fields/`)
- `CountryListView` (`/api/countries/`)
- `FileUploadPreviewView` (`/api/api-file-upload-preview/`)
- `WriteTableToDatabaseView` (`/api/api-write-table/`)
- `ListUploadedTablesView` (`/api/api-list-uploaded-tables/<project_id>/`)
- `GetTableDataView` (`/api/api-get-table-data/`)
- `GetDistinctValuesView` (`/api/api-get-distinct-values/`)
- `PreviewTableDataView` (`/api/api-preview-table-data/`)
- `UploadTableDataView` (`/api/api-upload-table-data/`)
- `CreateTableRecordView` (`/api/api-create-table-record/`)
- `EditTableRecordView` (`/api/api-edit-table-record/`)
- `DeleteTableRecordView` (`/api/api-delete-table-record/`)
- `UpdateTableStructureView` (`/api/api-update-table-structure/`)
- `DeleteTableView` (`/api/api-delete-table/`)
- `CreateTableWithoutRecordsView` (`/api/api-create-table/`)
- `ImportDataFromHanaView` (`/api/api-import-data-from-hana/`)
- `DownloadTableDataView` (`/api/api-download-table-data/`)
- `TruncateTableView` (`/api/api-truncate-table/`)
- `CreateUserView` (`/api/api-create-user/`)
- `UserListView` (`/api/api-list-users/`)
- `UserUpdateView` (`/api/api-update-user/<id>/`)
- `UserDeleteView` (`/api/api-delete-user/<id>/`)
- `UserPasswordResetView` (`/api/api-reset-password/`)
- `UserPasswordResetConfirmView` (`/api/api-reset-password-confirm/`)
- `ProjectsListView` (`/api/api-projects-list/`)
- `ColumnStatisticsView` (`/api/api-column-statistics/`)
- `ColumnSequenceListView` (`/api/api-column-sequence-list/`)
- `ColumnSequenceView` (`/api/api-column-sequence/`)
- `ValidationRulesView` (`/api/api-validation-rules/`)
- `AggregateXMLImportView` (`/api/xml-query/import/`)
- `AggregateXMLValidateView` (`/api/xml-query/validate/`)

### ViewSets (KEEP in api/views/)
- `CanvasViewSet` (`/api/canvas/`) - Keep in api/views/canvas_views.py
- `MigrationJobViewSet` (`/api/migration-jobs/`) - Keep in api/views/migration_views.py
- `MetadataViewSet` (`/api/metadata/`) - Keep in api/views/metadata_views.py
- `ProjectViewSet` (`/api/projects/`) - Keep in api/views/project_views.py
- `NodeCacheView`, `NodeCacheStatsView`, `NodeCacheCleanupView` (`/api/node-cache/`) - Can keep or move

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

### Phase 2: Extract React API Views from api/views.py

1. **Create react_api/views/auth.py**
   - Move `LoginView`, `LogoutView`, `RefreshTokenView` from `api/views.py`
   - Import shared utilities from `api` app (models, serializers)

2. **Create react_api/views/sources.py**
   - Move source-related views from `api/views.py`:
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
     - `SqlConnectionView`
     - `SourcesListView`
     - `SourceFieldsView`

3. **Create react_api/views/destinations.py**
   - Move destination-related views from `api/views.py`:
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
   - Or import them from existing files

7. **Create react_api/views/tables.py**
   - Move table management views from `api/views.py`:
     - `FileUploadPreviewView`
     - `WriteTableToDatabaseView`
     - `ListUploadedTablesView`
     - `GetTableDataView`
     - `GetDistinctValuesView`
     - `PreviewTableDataView`
     - `UploadTableDataView`
     - `CreateTableRecordView`
     - `EditTableRecordView`
     - `DeleteTableRecordView`
     - `UpdateTableStructureView`
     - `DeleteTableView`
     - `CreateTableWithoutRecordsView`
     - `ImportDataFromHanaView`
     - `DownloadTableDataView`
     - `TruncateTableView`

8. **Create react_api/views/users.py**
   - Move user management views from `api/views.py`:
     - `CreateUserView`
     - `UserListView`
     - `UserUpdateView`
     - `UserDeleteView`
     - `UserPasswordResetView`
     - `UserPasswordResetConfirmView`

9. **Create react_api/views/misc.py**
   - Move miscellaneous views from `api/views.py`:
     - `CountryListView`
     - `ProjectsListView`
     - `ColumnStatisticsView`
     - `ColumnSequenceListView`
     - `ColumnSequenceView`
     - `ValidationRulesView`
     - `AggregateXMLImportView`
     - `AggregateXMLValidateView`

10. **Create react_api/views/__init__.py**
    - Export all views for backward compatibility
    - Maintain existing import paths where possible

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

4. **Move authentications.py (if React-specific)**
   - `api/authentications.py` → `react_api/authentications.py`
   - Or keep in `api/` if shared with Django templates
   - Check if `frondendviews.py` uses it

### Phase 4: Move Shared Utility Functions

1. **Extract utility functions from api/views.py**
   - Functions like `generate_encryption_key`, `create_connection_config`, `test_database_connection`, etc.
   - Decide: Keep in `api/` if shared, or move to `react_api/utils/` if React-specific
   - Create `react_api/utils/helpers.py` if needed

### Phase 5: Create React API URLs

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
   - Keep ViewSet URLs (canvas, migration, metadata, projects) - these stay in api/

### Phase 6: Update Imports

1. **Update react_api/views/__init__.py**
   - Export all views for easy importing
   - Maintain backward compatibility where possible

2. **Update files that import from api.views**
   - Update imports to use `react_api.views` for React API endpoints
   - Keep imports from `api.views` for ViewSets and shared utilities
   - Update imports in React API views to use `api.models`, `api.serializers`, etc.

3. **Update shared utilities**
   - Ensure utility functions in `api` app can be imported by `react_api`
   - Functions like `ensure_user_has_customer`, `generate_encryption_key`, etc.

### Phase 7: Testing and Cleanup

1. **Test all React API endpoints**
   - Verify all endpoints work correctly
   - Check authentication flows
   - Test pipeline execution
   - Test source/destination operations

2. **Cleanup**
   - Remove moved views from `api/views.py` (or delete the file if empty)
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
- `react_api/views/tables.py`
- `react_api/views/users.py`
- `react_api/views/misc.py`
- `react_api/utils/__init__.py`
- `react_api/utils/compute_execution.py` (from `api/compute_execution.py`)
- `react_api/utils/calculated_column_evaluator.py` (from `api/calculated_column_evaluator.py`)
- `react_api/utils/filters.py` (from `api/filters.py`)
- `react_api/utils/helpers.py` (if needed for shared utility functions)

### Files to Modify
- `datamigrationapi/settings.py` - Add `'react_api'` to INSTALLED_APPS
- `datamigrationapi/urls.py` - Include `react_api.urls`
- `api/urls.py` - Remove React API URL patterns, keep template URLs and ViewSet URLs
- `api/views.py` - Remove React API views (extract to react_api)
- Files importing from `api.views` - Update to use `react_api.views` where appropriate

### Files to Delete (after migration)
- `api/compute_execution.py` (moved to `react_api/utils/`)
- `api/calculated_column_evaluator.py` (moved to `react_api/utils/`)
- `api/filters.py` (moved to `react_api/utils/`)
- `api/views.py` (if all views are moved, or keep empty file for backward compatibility)

### Files to Keep Unchanged
- `api/frondendviews.py` - Django template views (KEEP AS-IS)
- `api/templates/` - HTML templates (KEEP AS-IS)
- `api/models/` - Database models (KEEP - shared)
- `api/serializers/` - DRF serializers (KEEP - shared)
- `api/migrations/` - Database migrations (KEEP - shared)
- `api/admin.py` - Django admin (KEEP - shared)
- `api/apps.py` - Django app config (KEEP - shared)
- `api/management/` - Management commands (KEEP - shared)
- `api/services/` - Business logic services (KEEP - shared)
- `api/tasks/` - Celery tasks (KEEP - shared)
- `api/views/canvas_views.py` - ViewSet (KEEP)
- `api/views/migration_views.py` - ViewSet (KEEP)
- `api/views/metadata_views.py` - ViewSet (KEEP)
- `api/views/project_views.py` - ViewSet (KEEP)

## Benefits

1. **Clear Separation**: React API endpoints (JSON) and Django template views (HTML) are completely separated
2. **Better Organization**: React API views organized by domain (auth, sources, destinations, pipeline, tables, users)
3. **Easier Maintenance**: Smaller, focused files instead of one massive 13,000+ line file
4. **Scalability**: Easy to add new React API endpoints without cluttering existing files
5. **Better Testing**: Each module can be tested independently
6. **No Breaking Changes**: Django template views remain untouched
7. **Shared Resources**: Models, serializers, migrations stay in `api/` for both to use

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
/api/canvas/                 → api.views.canvas_views.CanvasViewSet (ViewSet - KEEP)
/api/migration-jobs/         → api.views.migration_views.MigrationJobViewSet (ViewSet - KEEP)
/api/login/                  → api.frondendviews.login_page (Django template - KEEP)
/api/customer/sources/       → api.frondendviews.customer_sources (Django template - KEEP)
```
