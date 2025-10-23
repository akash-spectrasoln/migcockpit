from django.urls import path
from .views import (
    ProjectsListView, SqlConnectionView, SourcesListView, SourceFieldsView,
    CountryListView, SourceConnectionCreateView, CustomerSourcesView, SourceEditView, SourceDeleteView, DestinationConnectionCreateView, CustomerDestinationsView, DestinationEditView, DestinationDeleteView, FileUploadPreviewView, WriteTableToDatabaseView, ListUploadedTablesView, GetTableDataView, GetDistinctValuesView, PreviewTableDataView, UploadTableDataView,
     CreateTableRecordView, EditTableRecordView, DeleteTableRecordView, UpdateTableStructureView, DeleteTableView, CreateTableWithoutRecordsView, ImportDataFromHanaView, DownloadTableDataView, LoginView, LogoutView,
     TruncateTableView, CreateUserView, UserListView, UserUpdateView, UserDeleteView, UserPasswordResetView, UserPasswordResetConfirmView, ProjectsListView, ColumnStatisticsView
)

urlpatterns = [
    # Authentication API endpoints
    path('api-login/', LoginView.as_view(), name='login-api'),
    path('api-logout/', LogoutView.as_view(), name='logout-api'),
    
    path('fetch/', SqlConnectionView.as_view()),
    path('sources/', SourcesListView.as_view()),
    path('sources/<int:source_id>/fields/', SourceFieldsView.as_view()),
    
    # Country API endpoints
    path('countries/', CountryListView.as_view(), name='country-list'),

    # Source API endpoints
    path('sources-connection/', SourceConnectionCreateView.as_view(), name='source-connection'),
    
    # Destination API endpoints
    path('destinations-connection/', DestinationConnectionCreateView.as_view(), name='destination-connection'),
    
    # Customer sources API endpoint
    path('api-customer/sources/', CustomerSourcesView.as_view(), name='customer-sources-api'),
    
    # Source edit API endpoint
    path('api-customer/sources/<int:source_id>/edit/', SourceEditView.as_view(), name='source-edit-api'),
    
    # Source delete API endpoint
    path('api-customer/sources/<int:source_id>/delete/', SourceDeleteView.as_view(), name='source-delete-api'),
    
    # Customer destinations API endpoint
    path('api-customer/destinations/', CustomerDestinationsView.as_view(), name='customer-destinations-api'),
    
    # Destination edit API endpoint
    path('api-customer/destinations/<int:destination_id>/edit/', DestinationEditView.as_view(), name='destination-edit-api'),
    
    # Destination delete API endpoint
    path('api-customer/destinations/<int:destination_id>/delete/', DestinationDeleteView.as_view(), name='destination-delete-api'),
    
    # File upload preview API endpoint
    path('api-file-upload-preview/', FileUploadPreviewView.as_view(), name='file-upload-preview-api'),
    
    
    # Write table to database API endpoint
    path('api-write-table/', WriteTableToDatabaseView.as_view(), name='write-table-api'),
    
    # Table management API endpoints
    path('api-list-uploaded-tables/<str:project_id>/', ListUploadedTablesView.as_view(), name='list-uploaded-tables-api'),
    path('api-get-table-data/', GetTableDataView.as_view(), name='get-table-data-api'),
    path('api-get-distinct-values/', GetDistinctValuesView.as_view(), name='get-distinct-values-api'),
    path('api-preview-table-data/', PreviewTableDataView.as_view(), name='preview-table-data-api'),
    path('api-upload-table-data/', UploadTableDataView.as_view(), name='upload-table-data-api'),
    
    # Table record management API endpoints
    path('api-create-table-record/', CreateTableRecordView.as_view(), name='create-table-record-api'),
    path('api-edit-table-record/', EditTableRecordView.as_view(), name='edit-table-record-api'),
    path('api-delete-table-record/', DeleteTableRecordView.as_view(), name='delete-table-record-api'),
    path('api-download-table-data/', DownloadTableDataView.as_view(), name='download-table-data-api'),
    
    # Table structure management API endpoint
    path('api-update-table-structure/', UpdateTableStructureView.as_view(), name='update-table-structure-api'),
    
    # Table deletion API endpoint
    path('api-delete-table/', DeleteTableView.as_view(), name='delete-table-api'),
    
    # Table creation API endpoint
    path('api-create-table/', CreateTableWithoutRecordsView.as_view(), name='create-table-api'),
    path('api-import-data-from-hana/', ImportDataFromHanaView.as_view(), name='import-data-from-hana-api'),
    path('api-truncate-table/', TruncateTableView.as_view()),
    path('api-create-user/', CreateUserView.as_view(), name='create-user-api'),
    path('api-list-users/', UserListView.as_view(), name='list-users-api'),
    path('api-update-user/<int:user_id>/', UserUpdateView.as_view(), name='update-user-api'),
    path('api-delete-user/<int:user_id>/', UserDeleteView.as_view(), name='delete-user-api'),
    path('api-reset-password/', UserPasswordResetView.as_view(), name='reset-password-api'),
    path('api-reset-password-confirm/', UserPasswordResetConfirmView.as_view(), name='reset-password-confirm-api'),
    path('api-projects-list/', ProjectsListView.as_view(), name='projects-list-api'),
    path('api-column-statistics/', ColumnStatisticsView.as_view(), name='api-column-statistics'),
]


from .frondendviews import ( login_page, sql_connection_form, source_connection_form, 
customer_sources, edit_source, destination_connection_form, customer_destinations,
edit_destination, file_upload, table_management, user_tables, table_data_display, create_table, 
import_data, table_navigation, customer_user_dashboard, users_list, create_user, edit_user, user_delete,
password_reset_request, password_reset_confirm, projects_list)

frontend_urlpatterns = [
    path('login/', login_page, name='login_page'),
    path('', sql_connection_form, name='sql_connection_form'),
    path('add-source/', source_connection_form, name='source_connection_form'),
    path('add-destination/', destination_connection_form, name='destination_connection_form'),
    path('customer/sources/', customer_sources, name='customer_sources'),
    path('customer/sources/<int:source_id>/edit/', edit_source, name='edit_source'),
    path('customer/destinations/', customer_destinations, name='customer_destinations'),
    path('customer/destinations/<int:destination_id>/edit/', edit_destination, name='edit_destination'),
    path('file-upload/', file_upload, name='file_upload'),
    path('table-management/', table_management, name='table_management'),
    path('user-tables/<str:project_id>/', user_tables, name='user_added_tables'),
    path('table-data/<str:project_id>/', table_data_display, name='table_data_display'),
    path('create-table/', create_table, name='create_table'),
    path('import-data/', import_data, name='import_data'),
    path('<str:project_id>/table-navigation/', table_navigation, name='table_navigation'),
    path('customer-user-dashboard/', customer_user_dashboard, name='customer_user_dashboard'),
    path('users-list/', users_list, name='users_list'),
    path('create-user/', create_user, name='create_user'),
    path('user-update/<int:user_id>/', edit_user, name='user_update'),
    path('user-delete/<int:user_id>/', user_delete, name='user_delete'),
    path('projects-list/', projects_list, name='projects_list'),
    path('reset-password/', password_reset_request, name='reset-password-page'),
    path('reset-password-confirm/<str:uidb64>/<str:token>/', password_reset_confirm, name='reset-password-confirm-page'),
]


urlpatterns += frontend_urlpatterns