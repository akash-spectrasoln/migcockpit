# Project Structure Documentation

## Table of Contents

1. [Overview](#overview)
2. [Directory Structure](#directory-structure)
3. [Backend Architecture](#backend-architecture)
4. [Frontend Architecture](#frontend-architecture)
5. [Module Organization](#module-organization)
6. [Import Patterns](#import-patterns)
7. [Naming Conventions](#naming-conventions)
8. [Best Practices](#best-practices)
9. [Adding New Code](#adding-new-code)

---

## Overview

The Data Migration Cockpit is a full-stack application built with:
- **Backend**: Django 4.2 + Django REST Framework
- **Frontend**: React 18 + TypeScript + Vite
- **Architecture**: Monolithic Django app with microservices for data processing

This document describes the refactored project structure designed for maintainability, scalability, and developer productivity.

---

## Directory Structure

```
migcockpit-qoder/
└── migcockpit/
    └── datamigration-migcockpit/          # Main project root
        ├── api/                           # Main Django application
        │   ├── models/                    # Data models (organized by domain)
        │   │   ├── __init__.py           # Exports all models
        │   │   ├── base.py               # Base models (User, Customer, etc.)
        │   │   ├── canvas.py             # Canvas-related models
        │   │   ├── migration_job.py      # Migration job models
        │   │   └── project.py            # Project models
        │   ├── views/                    # API views (organized by domain)
        │   │   ├── __init__.py           # Exports all views
        │   │   ├── auth.py               # Authentication views
        │   │   ├── connections.py        # Source/Destination connections
        │   │   ├── tables.py             # Table management views
        │   │   ├── users.py              # User management views
        │   │   ├── utils.py              # Utility views
        │   │   ├── canvas_views.py       # Canvas ViewSets
        │   │   ├── migration_views.py    # Migration ViewSets
        │   │   ├── project_views.py      # Project ViewSets
        │   │   ├── metadata_views.py     # Metadata ViewSets
        │   │   ├── node_cache_views.py   # Node cache views
        │   │   ├── expression_validation.py  # Expression validation
        │   │   └── expression_testing.py     # Expression testing
        │   ├── serializers/               # DRF serializers
        │   │   ├── __init__.py           # Exports all serializers
        │   │   ├── base_serializers.py   # Legacy serializers
        │   │   ├── canvas_serializers.py
        │   │   ├── migration_serializers.py
        │   │   └── project_serializers.py
        │   ├── services/                  # Business logic services
        │   │   ├── __init__.py           # Exports all services
        │   │   ├── encryption_service.py  # Encryption utilities
        │   │   ├── sqlserver_connector.py # SQL Server connector
        │   │   ├── hana_connector.py     # SAP HANA connector
        │   │   └── node_cache.py         # Node caching service
        │   ├── utils/                     # Utility functions
        │   │   ├── __init__.py
        │   │   ├── database.py           # Database utilities
        │   │   └── validators.py         # Validation utilities
        │   ├── permissions.py             # Custom permissions
        │   ├── authentications.py         # Custom authentication
        │   ├── filters.py                 # Query filters
        │   ├── admin.py                   # Django admin configuration
        │   ├── urls.py                    # URL routing
        │   └── apps.py                    # App configuration
        │
        ├── api_admin/                     # Admin Django app
        │   ├── models.py
        │   ├── views.py
        │   ├── serializers.py
        │   ├── urls.py
        │   └── templates/
        │
        ├── datamigrationapi/              # Django project configuration
        │   ├── settings.py                # Django settings (uses env vars)
        │   ├── urls.py                    # Root URL configuration
        │   ├── wsgi.py                    # WSGI configuration
        │   └── asgi.py                    # ASGI configuration
        │
        ├── frontend/                      # React frontend application
        │   ├── src/
        │   │   ├── components/            # React components
        │   │   │   ├── Canvas/           # Canvas-related components
        │   │   │   │   ├── nodes/        # Node components
        │   │   │   │   ├── panels/       # Configuration panels
        │   │   │   │   └── DataFlowCanvas.tsx
        │   │   │   ├── auth/             # Authentication components
        │   │   │   └── shared/          # Shared components
        │   │   ├── pages/                # Page components
        │   │   ├── hooks/                # Custom React hooks
        │   │   ├── services/             # API services
        │   │   │   ├── api.ts            # API client
        │   │   │   └── websocket.ts      # WebSocket client
        │   │   ├── store/                # State management (Zustand)
        │   │   ├── types/                # TypeScript type definitions
        │   │   ├── utils/                # Utility functions
        │   │   ├── constants/            # Constants
        │   │   ├── routes/               # Routing configuration
        │   │   └── theme/                # Theme configuration
        │   ├── package.json
        │   └── vite.config.ts
        │
        ├── services/                      # Microservices
        │   ├── extraction_service/        # Data extraction service
        │   │   ├── connectors/           # Database connectors
        │   │   ├── workers/              # Worker processes
        │   │   └── main.py
        │   ├── migration_service/         # Data migration service
        │   └── websocket_server/        # WebSocket server
        │
        ├── scripts/                       # Utility scripts
        │   ├── start_all_services.bat
        │   ├── start_all_services.ps1
        │   └── start_services.sh
        │
        ├── docs/                          # Documentation
        │   ├── PROJECT_STRUCTURE.md      # This file
        │   ├── DEVELOPER_GUIDE.md        # Developer guide
        │   ├── MIGRATION_GUIDE.md        # Migration guide
        │   └── ...                       # Other docs
        │
        ├── migrations/                    # SQL migrations
        ├── manage.py                      # Django management script
        ├── requirements.txt               # Python dependencies
        ├── .env.example                  # Environment variables template
        └── .gitignore                    # Git ignore rules
```

---

## Backend Architecture

### Models (`api/models/`)

Models are organized by domain to improve maintainability:

#### `base.py`
Contains core application models:
- `User` - Custom user model (email-based authentication)
- `Customer` - Customer/organization model
- `Country` - Country reference data
- `SourceDB` - Source database types
- `SourceForm` - Source form configurations
- `Roles` - User roles
- `UsrRoles` - User-role mappings
- `ValidationRules` - Data validation rules

**Import Pattern:**
```python
from api.models import User, Customer, Country
```

#### `canvas.py`
Canvas-related models:
- `Canvas` - Data flow canvas
- `CanvasNode` - Canvas nodes
- `CanvasEdge` - Canvas edges/connections

**Import Pattern:**
```python
from api.models import Canvas, CanvasNode, CanvasEdge
```

#### `migration_job.py`
Migration job models:
- `MigrationJob` - Migration job instance
- `MigrationJobLog` - Migration job logs

**Import Pattern:**
```python
from api.models import MigrationJob, MigrationJobLog
```

#### `project.py`
Project models:
- `Project` - Project/organization unit

**Import Pattern:**
```python
from api.models import Project
```

### Views (`api/views/`)

Views are organized by functional domain:

#### `auth.py`
Authentication and authorization:
- `LoginView` - User login
- `LogoutView` - User logout
- `RefreshTokenView` - Token refresh

#### `connections.py`
Source and destination connections:
- `SourceConnectionCreateView` - Create source connection
- `DestinationConnectionCreateView` - Create destination connection
- `SourceEditView` - Edit source connection
- `DestinationEditView` - Edit destination connection
- `CustomerSourcesView` - List customer sources
- `CustomerDestinationsView` - List customer destinations

#### `tables.py`
Table management:
- `ListUploadedTablesView` - List uploaded tables
- `GetTableDataView` - Get table data
- `CreateTableRecordView` - Create table record
- `UpdateTableStructureView` - Update table structure
- `DeleteTableView` - Delete table

#### `users.py`
User management:
- `CreateUserView` - Create user
- `UserListView` - List users
- `UserUpdateView` - Update user
- `UserDeleteView` - Delete user
- `UserPasswordResetView` - Password reset

#### `utils.py`
Utility views:
- `SqlConnectionView` - Test SQL connection
- `CountryListView` - List countries

#### ViewSets (REST Framework)
- `canvas_views.py` - `CanvasViewSet`
- `migration_views.py` - `MigrationJobViewSet`
- `project_views.py` - `ProjectViewSet`
- `metadata_views.py` - `MetadataViewSet`
- `node_cache_views.py` - Node cache views

**Import Pattern:**
```python
# From views package
from api.views import LoginView, SourceConnectionCreateView

# Or directly from module
from api.views.auth import LoginView
from api.views.connections import SourceConnectionCreateView
```

### Services (`api/services/`)

Business logic and external integrations:

#### `encryption_service.py`
Encryption utilities:
- `encrypt_field(value, cust_id, created_on)` - Encrypt field value
- `decrypt_field(encrypted_value, cust_id, created_on)` - Decrypt field value

#### `sqlserver_connector.py`
SQL Server connector:
- `extract_data(...)` - Extract data from SQL Server

#### `hana_connector.py`
SAP HANA connector:
- HANA connection and data operations

#### `node_cache.py`
Node caching service:
- Cache management for canvas nodes

**Import Pattern:**
```python
from api.services import encrypt_field, decrypt_field, extract_data
# Or
from api.services.encryption_service import encrypt_field
```

### Serializers (`api/serializers/`)

DRF serializers organized by domain:

- `base_serializers.py` - Legacy serializers
- `canvas_serializers.py` - Canvas serializers
- `migration_serializers.py` - Migration serializers
- `project_serializers.py` - Project serializers

**Import Pattern:**
```python
from api.serializers import CanvasSerializer, ProjectSerializer
```

---

## Frontend Architecture

### Components (`frontend/src/components/`)

#### `Canvas/`
Canvas-related components:
- `DataFlowCanvas.tsx` - Main canvas component
- `nodes/` - Node components (ProjectionNode, FilterNode, etc.)
- `panels/` - Configuration panels (ProjectionConfigPanel, etc.)

#### `auth/`
Authentication components:
- `ProtectedRoute.tsx` - Route protection component

#### `shared/`
Reusable components:
- `ErrorMessage.tsx` - Error display component
- `Spinner.tsx` - Loading spinner

### Pages (`frontend/src/pages/`)

Page-level components:
- `CanvasPage.tsx` - Canvas page
- `DashboardPage.tsx` - Dashboard page
- `LoginPage.tsx` - Login page
- `ProjectsListPage.tsx` - Projects list page

### Services (`frontend/src/services/`)

API and WebSocket clients:
- `api.ts` - Main API client (re-exports from lib/axios)
- `websocket.ts` - WebSocket client

### Store (`frontend/src/store/`)

State management (Zustand):
- `canvasStore.ts` - Canvas state management
- `authStore.ts` - Authentication state management

### Types (`frontend/src/types/`)

TypeScript type definitions:
- `nodeRegistry.ts` - Node type definitions

---

## Module Organization

### Principles

1. **Domain-Driven Organization**: Group related functionality together
2. **Single Responsibility**: Each module has a clear, single purpose
3. **Explicit Exports**: Use `__init__.py` files to control public API
4. **Consistent Naming**: Follow Python/TypeScript naming conventions

### Module Structure Pattern

Each module follows this pattern:

```
module_name/
├── __init__.py          # Exports public API
├── core.py              # Core functionality
├── utils.py             # Utility functions (if needed)
└── exceptions.py        # Custom exceptions (if needed)
```

---

## Import Patterns

### Backend (Python)

#### Absolute Imports (Preferred)
```python
# Models
from api.models import User, Customer, Canvas

# Views
from api.views.auth import LoginView
from api.views.connections import SourceConnectionCreateView

# Services
from api.services import encrypt_field, decrypt_field

# Serializers
from api.serializers import CanvasSerializer
```

#### Relative Imports (Within Same Package)
```python
# Within api/views/
from .auth import LoginView
from .connections import SourceConnectionCreateView
```

### Frontend (TypeScript)

#### Absolute Imports (via path aliases)
```typescript
// Components
import { ProjectionConfigPanel } from '@/components/Canvas/panels/ProjectionConfigPanel'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'

// Services
import { api, canvasApi } from '@/services/api'

// Types
import { CanvasNode } from '@/types/nodeRegistry'

// Utils
import { formatDate } from '@/utils/date'
```

#### Relative Imports (Within Same Directory)
```typescript
// Within components/Canvas/
import { ProjectionNode } from './nodes/ProjectionNode'
import { FilterNode } from './nodes/FilterNode'
```

---

## Naming Conventions

### Backend (Python)

- **Files**: `snake_case.py` (e.g., `encryption_service.py`)
- **Classes**: `PascalCase` (e.g., `SourceConnectionCreateView`)
- **Functions**: `snake_case` (e.g., `encrypt_field`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_COUNT`)
- **Private**: Prefix with `_` (e.g., `_internal_helper`)

### Frontend (TypeScript)

- **Files**: `PascalCase.tsx` for components, `camelCase.ts` for utilities
- **Components**: `PascalCase` (e.g., `ProjectionConfigPanel`)
- **Functions**: `camelCase` (e.g., `formatDate`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `API_BASE_URL`)
- **Types/Interfaces**: `PascalCase` (e.g., `CanvasNodeData`)

---

## Best Practices

### Backend

1. **Models**: Keep models focused on data structure, move business logic to services
2. **Views**: Keep views thin, delegate to services
3. **Services**: Contain business logic and external integrations
4. **Serializers**: Handle data validation and transformation
5. **Utils**: Pure utility functions with no side effects

### Frontend

1. **Components**: Keep components focused and reusable
2. **Hooks**: Extract reusable logic into custom hooks
3. **Services**: Centralize API calls
4. **Store**: Use Zustand for global state, local state for component-specific state
5. **Types**: Define types close to where they're used

### General

1. **DRY**: Don't repeat yourself - extract common code
2. **SOLID**: Follow SOLID principles
3. **Testing**: Write tests for critical functionality
4. **Documentation**: Document complex logic and public APIs
5. **Git**: Commit frequently with descriptive messages

---

## Adding New Code

### Adding a New Model

1. **Determine Domain**: Choose appropriate file in `api/models/`
2. **Create Model**: Add model class to appropriate file
3. **Export**: Add to `api/models/__init__.py`
4. **Admin**: Register in `api/admin.py`
5. **Serializer**: Create serializer in `api/serializers/`
6. **Migration**: Run `python manage.py makemigrations`

**Example:**
```python
# api/models/base.py
class NewModel(models.Model):
    name = models.CharField(max_length=100)
    # ...

# api/models/__init__.py
from .base import NewModel
__all__ = [..., 'NewModel']
```

### Adding a New View

1. **Determine Domain**: Choose appropriate file in `api/views/`
2. **Create View**: Add view class to appropriate file
3. **Export**: Add to `api/views/__init__.py`
4. **URL**: Add route in `api/urls.py`
5. **Serializer**: Use or create serializer

**Example:**
```python
# api/views/utils.py
class NewUtilityView(APIView):
    def get(self, request):
        # ...

# api/views/__init__.py
from .utils import NewUtilityView
__all__ = [..., 'NewUtilityView']

# api/urls.py
path('new-utility/', NewUtilityView.as_view()),
```

### Adding a New Service

1. **Create File**: Create new file in `api/services/`
2. **Implement Functions**: Add service functions
3. **Export**: Add to `api/services/__init__.py`

**Example:**
```python
# api/services/new_service.py
def new_service_function(param):
    # ...
    return result

# api/services/__init__.py
from .new_service import new_service_function
__all__ = [..., 'new_service_function']
```

### Adding a New Frontend Component

1. **Determine Location**: Choose appropriate directory
2. **Create Component**: Create component file
3. **Export**: Add to index file if needed
4. **Types**: Define TypeScript types
5. **Styling**: Use Chakra UI components

**Example:**
```typescript
// frontend/src/components/shared/NewComponent.tsx
export const NewComponent: React.FC<Props> = ({ prop }) => {
  return <Box>...</Box>
}
```

---

## Configuration Management

### Environment Variables

All configuration is managed via environment variables:

**File**: `.env` (not committed to git)
**Template**: `.env.example`

**Key Variables:**
- `DATABASE_NAME` - Database name
- `DATABASE_USER` - Database user
- `DATABASE_PASSWORD` - Database password
- `SECRET_KEY` - Django secret key
- `DEBUG` - Debug mode (True/False)
- `ALLOWED_HOSTS` - Allowed hosts (comma-separated)

**Usage in settings.py:**
```python
from decouple import config

DATABASES = {
    'default': {
        'NAME': config('DATABASE_NAME'),
        'USER': config('DATABASE_USER'),
        'PASSWORD': config('DATABASE_PASSWORD'),
        # ...
    }
}
```

---

## Testing Structure

### Backend Tests

```
api/
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_views.py
│   ├── test_serializers.py
│   ├── test_services.py
│   └── fixtures/
│       └── test_data.json
```

### Frontend Tests

```
frontend/
├── src/
└── __tests__/
    ├── components/
    ├── pages/
    └── utils/
```

---

## Migration Notes

### From Old Structure

If migrating from the old structure:

1. **Models**: `api/models.py` → `api/models/base.py` (and other files)
2. **Views**: `api/views.py` → `api/views/*.py` (organized by domain)
3. **Services**: Root-level modules → `api/services/`

See `MIGRATION_GUIDE.md` for detailed migration instructions.

---

## Additional Resources

- **Developer Guide**: `docs/DEVELOPER_GUIDE.md`
- **Migration Guide**: `docs/MIGRATION_GUIDE.md`
- **API Documentation**: `docs/API_Documentation.xlsx`
- **Architecture**: `docs/CANVAS_ARCHITECTURE.md`

---

## Questions?

For questions about the project structure, please refer to:
1. This documentation
2. Developer Guide (`docs/DEVELOPER_GUIDE.md`)
3. Team lead or senior developers

