"""
Import all views
This module re-exports views from organized submodules (auth.py, users.py, sources.py, etc.)
All views have been extracted from the monolithic views.py into domain-specific modules.
"""

# Import from submodules
from .auth import LoginView, LogoutView, RefreshTokenView
from .users import (
    CreateUserView, UserListView, UserUpdateView, UserDeleteView,
    UserPasswordResetView, UserPasswordResetConfirmView
)
from .sources import (
    SqlConnectionView, SourcesListView, SourceFieldsView, CountryListView,
    SourceConnectionCreateView, CustomerSourcesView, SourceAttributesView,
    SourceConnectionCreateWithValidationView, SourceEditView, SourceDeleteView,
    SourceTablesView, SourceTableDataView, SourceColumnsView, SourceTableSelectionView,
    SourceLiveSchemaView,
)
from .destinations import (
    DestinationConnectionCreateView, CustomerDestinationsView,
    DestinationEditView, DestinationDeleteView, DestinationTablesView
)
from .projects import ProjectsListView
from .misc import AggregateXMLImportView, AggregateXMLValidateView
from .utils import ValidationRulesView

# Pipeline views
from .pipeline import FilterExecutionView, JoinExecutionView, PipelineQueryExecutionView

# Expression views
from .expression import (
    FilterColumnValuesView,
    ColumnStatisticsView,
    ColumnSequenceListView,
    ColumnSequenceView
)

# Table views
from .tables import (
    FileUploadPreviewView,
    WriteTableToDatabaseView,
    ListUploadedTablesView,
    GetTableDataView,
    GetDistinctValuesView,
    PreviewTableDataView,
    UploadTableDataView,
    CreateTableRecordView,
    EditTableRecordView,
    DeleteTableRecordView,
    UpdateTableStructureView,
    DeleteTableView,
    CreateTableWithoutRecordsView,
    ImportDataFromHanaView,
    DownloadTableDataView,
    TruncateTableView
)
from .canvas_views import CanvasViewSet
from .migration_views import MigrationJobViewSet

__all__ = [
    # Auth views
    'LoginView', 'LogoutView', 'RefreshTokenView',
    # User views
    'CreateUserView', 'UserListView', 'UserUpdateView', 'UserDeleteView',
    'UserPasswordResetView', 'UserPasswordResetConfirmView',
    # Source views
    'SqlConnectionView', 'SourcesListView', 'SourceFieldsView', 'CountryListView',
    'SourceConnectionCreateView', 'CustomerSourcesView', 'SourceAttributesView',
    'SourceConnectionCreateWithValidationView', 'SourceEditView', 'SourceDeleteView',
    'SourceTablesView', 'SourceTableDataView', 'SourceColumnsView', 'SourceTableSelectionView',
    'SourceLiveSchemaView',
    # Destination views
    'DestinationConnectionCreateView', 'CustomerDestinationsView',
    'DestinationEditView', 'DestinationDeleteView', 'DestinationTablesView',
    # Project views
    'ProjectsListView',
    # Misc views
    'AggregateXMLImportView', 'AggregateXMLValidateView',
    # Pipeline views
    'FilterExecutionView', 'JoinExecutionView', 'PipelineQueryExecutionView',
    # Expression views
    'FilterColumnValuesView', 'ColumnStatisticsView', 'ColumnSequenceListView', 'ColumnSequenceView',
    # Table views
    'FileUploadPreviewView', 'WriteTableToDatabaseView', 'ListUploadedTablesView',
    'GetTableDataView', 'GetDistinctValuesView', 'PreviewTableDataView', 'UploadTableDataView',
    'CreateTableRecordView', 'EditTableRecordView', 'DeleteTableRecordView',
    'UpdateTableStructureView', 'DeleteTableView', 'CreateTableWithoutRecordsView',
    'ImportDataFromHanaView', 'DownloadTableDataView', 'TruncateTableView',
    # Utility views
    'ValidationRulesView',
    # Canvas views
    'CanvasViewSet',
    # Migration views
    'MigrationJobViewSet'
]

