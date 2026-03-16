"""
DEPRECATED: This file has been refactored.

All views have been extracted into organized modules:
- api/views/auth.py - Authentication views
- api/views/users.py - User management views
- api/views/sources.py - Source connection views
- api/views/destinations.py - Destination connection views
- api/views/projects.py - Project views
- api/views/misc.py - Miscellaneous views (XML parsing, aggregate validation)
- api/views/pipeline.py - Pipeline execution views
- api/views/expression.py - Expression/column views
- api/views/tables.py - Table management views
- api/views/utils.py - Validation rules view

All utility functions have been moved to:
- api/utils/helpers.py - Helper functions
- api/utils/filters.py - Filter utilities
- api/utils/calculated_column_evaluator.py - Calculated column evaluation
- api/utils/compute_execution.py - Compute node execution

This file is kept for reference only and should not be imported from.
All imports should use: from api.views import <ViewName>
which will resolve to the organized modules via api/views/__init__.py
"""

# This file is intentionally empty - all code has been moved to organized modules
# See api/views/__init__.py for the import structure
