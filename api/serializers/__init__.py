"""
Serializers module
This module re-exports serializers from base_serializers.py and submodules
"""

# Import legacy serializers from base_serializers
from .base_serializers import (
    SqlConnectionSerializer,
    SourceDbSerializer,
    SourceFormSerializer,
    ValidationRulesSerializer,
    CountrySerializer,
    SourceConnectionSerializer,
    DestinationConnectionSerializer,
    FileUploadSerializer,
    CustomerSerializer,
    UserSerializer
)

# Import new serializers
from .canvas_serializers import CanvasSerializer, CanvasCreateSerializer, CanvasNodeSerializer, CanvasEdgeSerializer
from .migration_serializers import MigrationJobSerializer, MigrationJobListSerializer, MigrationJobCreateSerializer, MigrationJobLogSerializer, MigrationJobStatusSerializer
from .project_serializers import ProjectSerializer, ProjectCreateSerializer, ProjectDetailSerializer

__all__ = [
    # Legacy
    'SqlConnectionSerializer', 'SourceDbSerializer', 'SourceFormSerializer', 
    'ValidationRulesSerializer', 'CountrySerializer', 'SourceConnectionSerializer', 
    'DestinationConnectionSerializer', 'FileUploadSerializer', 'CustomerSerializer', 
    'UserSerializer',
    
    # New
    'CanvasSerializer', 'CanvasCreateSerializer', 'CanvasNodeSerializer', 'CanvasEdgeSerializer',
    'MigrationJobSerializer', 'MigrationJobListSerializer', 'MigrationJobCreateSerializer', 'MigrationJobLogSerializer', 'MigrationJobStatusSerializer',
    'ProjectSerializer', 'ProjectCreateSerializer', 'ProjectDetailSerializer'
]

