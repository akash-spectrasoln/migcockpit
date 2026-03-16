# Database Connection Utility - Refactoring Guide

## Overview
The `api/utils/db_connection.py` module provides centralized database connection configuration for customer databases.

## Current Status
✅ **Created**: `api/utils/db_connection.py`
✅ **Refactored**: `api/views/metadata_views.py` (validate_pipeline endpoint)

## Files Still Using Inline Connection Config
The following files still construct connection configs inline and should be refactored to use the centralized utility:

### High Priority (Frequently Used)
- `api/views/pipeline.py` - 9 occurrences
- `api/views/tables.py` - 13 occurrences  
- `api/views/sources.py` - 12 occurrences

### Medium Priority
- `api/views/expression.py` - 6 occurrences
- `api/views/destinations.py` - 6 occurrences
- `api/utils/sql_compiler.py` - 1+ occurrences
- `api/utils/db_executor.py` - 1+ occurrences

### Low Priority
- `api/views/projects.py` - 1 occurrence

## Refactoring Pattern

### Before (Inline Config):
```python
from django.conf import settings
from api.models import Customer

customer = Customer.objects.get(...)
connection_config = {
    "host": settings.DATABASES['default']['HOST'],
    "port": settings.DATABASES['default']['PORT'],
    "database": customer.cust_db,
    "user": settings.DATABASES['default']['USER'],
    "password": settings.DATABASES['default']['PASSWORD']
}
```

### After (Using Utility - Sync):
```python
from api.utils.db_connection import get_customer_db_config_from_request

connection_config = get_customer_db_config_from_request(request)
```

### After (Using Utility - Async):
```python
from api.utils.db_connection import get_customer_db_config_from_request_async

connection_config = await get_customer_db_config_from_request_async(request)
```

### After (Direct DB Name):
```python
from api.utils.db_connection import get_customer_db_config

connection_config = get_customer_db_config('cust_db_123')
```

## Benefits
1. **DRY Principle**: Single source of truth for connection configuration
2. **Maintainability**: Changes to connection logic only need to be made in one place
3. **Consistency**: All parts of the application use the same connection strategy
4. **Async Safety**: Built-in async support with `sync_to_async` wrapper
5. **Error Handling**: Centralized logging and error handling

## Next Steps
1. Gradually refactor high-priority files
2. Test each refactored endpoint thoroughly
3. Update this document as files are refactored
4. Eventually deprecate inline connection config pattern
