# Reorganize API Directory - Better Structure Within Same App

## Current Problems

1. **api/views.py** - Massive file (13,000+ lines) with all API views mixed together
2. **Scattered files** - Utility files like `compute_execution.py`, `calculated_column_evaluator.py`, `filters.py` at root level
3. **Poor organization** - Hard to find specific views, difficult to maintain

## Solution: Organize Within Same `api/` App

Keep everything in `api/` but organize it better by:
1. Breaking down `api/views.py` into organized modules in `api/views/`
2. Moving utility files to `api/utils/`
3. Keeping Django template views (`frondendviews.py`) and templates as-is
4. Better file structure for maintainability

## Proposed Structure

```
datamigration-migcockpit/
├── api/
│   ├── __init__.py
│   ├── apps.py
│   ├── admin.py
│   ├── authentications.py          # Keep as-is (used by both)
│   ├── utilts.py                   # Keep as-is (shared utilities)
│   │
│   ├── frondendviews.py            # Django template views (KEEP AS-IS)
│   ├── templates/                  # HTML templates (KEEP AS-IS)
│   │
│   ├── views/                       # Organized API views (NEW STRUCTURE)
│   │   ├── __init__.py             # Export all views for backward compatibility
│   │   ├── auth.py                 # Authentication APIs
│   │   │   - LoginView
│   │   │   - LogoutView
│   │   │   - RefreshTokenView
│   │   │
│   │   ├── sources.py              # Source APIs
│   │   │   - CustomerSourcesView
│   │   │   - SourceEditView
│   │   │   - SourceDeleteView
│   │   │   - SourceTablesView
│   │   │   - SourceTableSelectionView
│   │   │   - SourceTableDataView
│   │   │   - SourceColumnsView
│   │   │   - SourceConnectionCreateView
│   │   │   - SourceConnectionCreateWithValidationView
│   │   │   - SourceAttributesView
│   │   │   - FilterExecutionView
│   │   │   - JoinExecutionView
│   │   │   - SqlConnectionView
│   │   │   - SourcesListView
│   │   │   - SourceFieldsView
│   │   │
│   │   ├── destinations.py         # Destination APIs
│   │   │   - CustomerDestinationsView
│   │   │   - DestinationEditView
│   │   │   - DestinationDeleteView
│   │   │   - DestinationConnectionCreateView
│   │   │
│   │   ├── pipeline.py             # Pipeline execution APIs
│   │   │   - PipelineQueryExecutionView
│   │   │
│   │   ├── compute.py              # Compute node APIs
│   │   │   - ComputeNodeExecutionView
│   │   │   - ComputeNodeCompileView
│   │   │
│   │   ├── expression.py           # Expression validation APIs
│   │   │   - ValidateExpressionView (from views/expression_validation.py)
│   │   │   - TestExpressionView (from views/expression_testing.py)
│   │   │
│   │   ├── tables.py               # Table management APIs
│   │   │   - FileUploadPreviewView
│   │   │   - WriteTableToDatabaseView
│   │   │   - ListUploadedTablesView
│   │   │   - GetTableDataView
│   │   │   - GetDistinctValuesView
│   │   │   - PreviewTableDataView
│   │   │   - UploadTableDataView
│   │   │   - CreateTableRecordView
│   │   │   - EditTableRecordView
│   │   │   - DeleteTableRecordView
│   │   │   - UpdateTableStructureView
│   │   │   - DeleteTableView
│   │   │   - CreateTableWithoutRecordsView
│   │   │   - ImportDataFromHanaView
│   │   │   - DownloadTableDataView
│   │   │   - TruncateTableView
│   │   │
│   │   ├── users.py                # User management APIs
│   │   │   - CreateUserView
│   │   │   - UserListView
│   │   │   - UserUpdateView
│   │   │   - UserDeleteView
│   │   │   - UserPasswordResetView
│   │   │   - UserPasswordResetConfirmView
│   │   │
│   │   ├── projects.py             # Project APIs
│   │   │   - ProjectsListView
│   │   │
│   │   ├── misc.py                 # Miscellaneous APIs
│   │   │   - CountryListView
│   │   │   - ColumnStatisticsView
│   │   │   - ColumnSequenceListView
│   │   │   - ColumnSequenceView
│   │   │   - ValidationRulesView
│   │   │   - AggregateXMLImportView
│   │   │   - AggregateXMLValidateView
│   │   │
│   │   ├── canvas_views.py         # Canvas ViewSet (EXISTING - KEEP)
│   │   ├── migration_views.py      # Migration ViewSet (EXISTING - KEEP)
│   │   ├── metadata_views.py        # Metadata ViewSet (EXISTING - KEEP)
│   │   ├── project_views.py        # Project ViewSet (EXISTING - KEEP)
│   │   ├── node_cache_views.py     # Node Cache APIs (EXISTING - KEEP)
│   │   ├── expression_validation.py  # Expression validation (EXISTING - KEEP)
│   │   ├── expression_testing.py     # Expression testing (EXISTING - KEEP)
│   │   └── utils.py                # Utility APIs (EXISTING - KEEP)
│   │
│   ├── utils/                       # Utility modules (NEW)
│   │   ├── __init__.py
│   │   ├── compute_execution.py     # Moved from api/compute_execution.py
│   │   ├── calculated_column_evaluator.py  # Moved from api/calculated_column_evaluator.py
│   │   └── filters.py              # Moved from api/filters.py
│   │
│   ├── serializers/                 # DRF serializers (EXISTING - KEEP)
│   ├── models/                      # Database models (EXISTING - KEEP)
│   ├── migrations/                  # Database migrations (EXISTING - KEEP)
│   ├── services/                    # Business logic services (EXISTING - KEEP)
│   ├── tasks/                       # Celery tasks (EXISTING - KEEP)
│   ├── management/                  # Management commands (EXISTING - KEEP)
│   │
│   └── urls.py                      # URL routing (UPDATE imports)
```

## Implementation Steps

### Phase 1: Create Directory Structure

1. **Create `api/utils/` directory**
   ```bash
   mkdir api/utils
   ```

2. **Create `api/views/` subdirectories** (if needed)
   - Most views will go directly in `api/views/` as modules

### Phase 2: Extract Views from api/views.py

1. **Create api/views/auth.py**
   - Extract `LoginView`, `LogoutView`, `RefreshTokenView` from `api/views.py`
   - Import shared utilities from `api.utils` or `api`

2. **Create api/views/sources.py**
   - Extract all source-related views from `api/views.py`
   - Include utility functions if they're source-specific

3. **Create api/views/destinations.py**
   - Extract destination-related views from `api/views.py`

4. **Create api/views/pipeline.py**
   - Extract `PipelineQueryExecutionView` from `api/views.py`
   - This is a large view, keep it in one file

5. **Create api/views/compute.py**
   - Extract `ComputeNodeExecutionView` and `ComputeNodeCompileView` from `api/compute_execution.py`
   - Import from `api.utils.compute_execution` for shared logic

6. **Create api/views/expression.py**
   - Move `ValidateExpressionView` from `api/views/expression_validation.py` (or keep it there and import)
   - Move `TestExpressionView` from `api/views/expression_testing.py` (or keep it there and import)
   - Or consolidate expression views here

7. **Create api/views/tables.py**
   - Extract all table management views from `api/views.py`

8. **Create api/views/users.py**
   - Extract user management views from `api/views.py`

9. **Create api/views/projects.py**
   - Extract `ProjectsListView` from `api/views.py`

10. **Create api/views/misc.py**
    - Extract miscellaneous views from `api/views.py`

11. **Create api/views/__init__.py**
    - Export all views for backward compatibility
    - Maintain existing import paths: `from api.views import X`

### Phase 3: Move Utility Modules

1. **Move compute_execution.py**
   - `api/compute_execution.py` → `api/utils/compute_execution.py`
   - Update imports in `api/views/compute.py`

2. **Move calculated_column_evaluator.py**
   - `api/calculated_column_evaluator.py` → `api/utils/calculated_column_evaluator.py`
   - Update imports in `api/views/pipeline.py`

3. **Move filters.py**
   - `api/filters.py` → `api/utils/filters.py`
   - Update imports where used

### Phase 4: Extract Shared Utility Functions

1. **Create api/utils/helpers.py** (if needed)
   - Extract shared utility functions from `api/views.py`:
     - `generate_encryption_key`
     - `create_connection_config`
     - `test_database_connection`
     - `test_sqlserver_connection`
     - `test_postgresql_connection`
     - `convert_user_date_format_to_strftime`
     - `format_date_columns`
     - `decrypt_source_data`
     - `ensure_user_has_customer`

### Phase 5: Update Imports

1. **Update api/views/__init__.py**
   - Export all views from submodules
   - Maintain backward compatibility: `from api.views import LoginView` should still work

2. **Update api/urls.py**
   - Update imports to use new module paths:
     ```python
     from .views.auth import LoginView, LogoutView, RefreshTokenView
     from .views.sources import CustomerSourcesView, SourceEditView, ...
     from .views.destinations import CustomerDestinationsView, ...
     from .views.pipeline import PipelineQueryExecutionView
     from .views.compute import ComputeNodeExecutionView, ComputeNodeCompileView
     from .views.expression import ValidateExpressionView, TestExpressionView
     from .views.tables import FileUploadPreviewView, ...
     from .views.users import CreateUserView, UserListView, ...
     from .views.projects import ProjectsListView
     from .views.misc import CountryListView, ColumnStatisticsView, ...
     ```

3. **Update files importing from api.views**
   - Most imports should still work via `api/views/__init__.py`
   - Update direct imports if needed

### Phase 6: Testing and Cleanup

1. **Test all endpoints**
   - Verify all API endpoints work correctly
   - Test Django template views
   - Test React frontend integration

2. **Cleanup**
   - Delete `api/views.py` (after extracting all views)
   - Delete `api/compute_execution.py` (moved to `api/utils/`)
   - Delete `api/calculated_column_evaluator.py` (moved to `api/utils/`)
   - Delete `api/filters.py` (moved to `api/utils/`)
   - Update documentation

## Files to Create

### New Files
- `api/utils/__init__.py`
- `api/utils/compute_execution.py` (from `api/compute_execution.py`)
- `api/utils/calculated_column_evaluator.py` (from `api/calculated_column_evaluator.py`)
- `api/utils/filters.py` (from `api/filters.py`)
- `api/utils/helpers.py` (if needed for shared utilities)
- `api/views/auth.py`
- `api/views/sources.py`
- `api/views/destinations.py`
- `api/views/pipeline.py`
- `api/views/compute.py`
- `api/views/expression.py`
- `api/views/tables.py`
- `api/views/users.py`
- `api/views/projects.py`
- `api/views/misc.py`
- `api/views/__init__.py` (update existing)

### Files to Modify
- `api/urls.py` - Update imports to use new module paths
- `api/views/__init__.py` - Export all views for backward compatibility
- Files importing from `api.views` - May need minor updates

### Files to Delete (after migration)
- `api/views.py` (after extracting all views)
- `api/compute_execution.py` (moved to `api/utils/`)
- `api/calculated_column_evaluator.py` (moved to `api/utils/`)
- `api/filters.py` (moved to `api/utils/`)

### Files to Keep Unchanged
- `api/frondendviews.py` - Django template views (KEEP AS-IS)
- `api/templates/` - HTML templates (KEEP AS-IS)
- `api/views/canvas_views.py` - ViewSet (KEEP)
- `api/views/migration_views.py` - ViewSet (KEEP)
- `api/views/metadata_views.py` - ViewSet (KEEP)
- `api/views/project_views.py` - ViewSet (KEEP)
- `api/views/node_cache_views.py` - Node Cache APIs (KEEP)
- `api/views/expression_validation.py` - Expression validation (KEEP or consolidate)
- `api/views/expression_testing.py` - Expression testing (KEEP or consolidate)
- `api/views/utils.py` - Utility APIs (KEEP)
- All other existing files (models, serializers, migrations, services, tasks, etc.)

## Benefits

1. **Better Organization**: Views organized by domain (auth, sources, destinations, pipeline, etc.)
2. **Easier Maintenance**: Smaller, focused files instead of one massive 13,000+ line file
3. **Easier Navigation**: Find specific views quickly by domain
4. **Scalability**: Easy to add new views without cluttering existing files
5. **Better Testing**: Each module can be tested independently
6. **No Breaking Changes**: Backward compatibility maintained through `__init__.py` exports
7. **Same App**: Everything stays in `api/` app, simpler structure
8. **Django Templates Unchanged**: Template views remain as-is

## Migration Strategy

- **Backward Compatibility**: Use `api/views/__init__.py` to maintain existing imports
- **Gradual Migration**: Can be done incrementally, testing after each phase
- **No Breaking Changes**: All existing URLs and imports continue to work
- **Simple Structure**: Everything in one app, just better organized
