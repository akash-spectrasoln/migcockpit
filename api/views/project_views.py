"""
Project API Views
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from api.models.project import Project
from api.models.canvas import Canvas
from api.serializers.project_serializers import (
    ProjectSerializer,
    ProjectCreateSerializer,
    ProjectDetailSerializer
)
from api.authentications import JWTCookieAuthentication
import logging

# Import ensure_user_has_customer - using late import to avoid circular dependency
def get_ensure_user_has_customer():
    from api.utils.helpers import ensure_user_has_customer
    return ensure_user_has_customer

logger = logging.getLogger(__name__)


class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Project CRUD operations
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    authentication_classes = [JWTCookieAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Use different serializer for create and retrieve"""
        if self.action == 'create':
            return ProjectCreateSerializer
        elif self.action == 'retrieve':
            return ProjectDetailSerializer
        return ProjectSerializer
    
    def get_queryset(self):
        """Filter projects by customer"""
        try:
            # Check if project table exists by trying a simple query
            # This handles the case where migrations haven't created the table
            try:
                Project.objects.exists()
            except Exception as table_error:
                logger.warning(f"Project table may not exist: {table_error}")
                return Project.objects.none()
            
            user = self.request.user
            if user.is_superuser:
                return Project.objects.filter(is_active=True)
            
            # Ensure user has a customer
            ensure_user_has_customer = get_ensure_user_has_customer()
            customer = ensure_user_has_customer(user)
            if customer:
                return Project.objects.filter(customer=customer, is_active=True)
            return Project.objects.none()
        except Exception as e:
            logger.error(f"Error in get_queryset: {e}")
            return Project.objects.none()
    
    def perform_create(self, serializer):
        """Set customer from user"""
        user = self.request.user
        ensure_user_has_customer = get_ensure_user_has_customer()
        customer = ensure_user_has_customer(user)
        if customer:
            serializer.save(customer=customer)
        else:
            serializer.save()
    
    def perform_destroy(self, instance):
        """
        Soft delete project by setting is_active=False
        This preserves data integrity and allows recovery
        """
        instance.is_active = False
        instance.save()
    
    @action(detail=True, methods=['get'])
    def canvases(self, request, pk=None):
        """Get all canvases for this project"""
        project = self.get_object()
        canvases = Canvas.objects.filter(project_id=project.project_id, is_active=True)
        from api.serializers.canvas_serializers import CanvasSerializer
        serializer = CanvasSerializer(canvases, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get project statistics"""
        project = self.get_object()
        
        canvas_count = Canvas.objects.filter(project_id=project.project_id, is_active=True).count()
        
        # Source and destination counts will be calculated via API calls to customer database
        # For now, return placeholder values
        stats = {
            'canvas_count': canvas_count,
            'source_count': 0,  # Will be calculated via API
            'destination_count': 0,  # Will be calculated via API
        }
        
        return Response(stats)

