"""
Node Cache API Views

Views for managing and accessing node transformation caches.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from api.authentications import JWTCookieAuthentication
from api.services.node_cache import get_node_cache_manager
import logging

logger = logging.getLogger(__name__)

# Import ensure_user_has_customer - using late import to avoid circular dependency
def get_ensure_user_has_customer():
    from api.utils.helpers import ensure_user_has_customer
    return ensure_user_has_customer


class NodeCacheView(APIView):
    """
    API view for node cache operations.
    
    GET /api/node-cache/<canvas_id>/<node_id>/
        Get cached data for a specific node
        
    POST /api/node-cache/<canvas_id>/<node_id>/
        Save node data to cache
        
    DELETE /api/node-cache/<canvas_id>/<node_id>/
        Invalidate cache for a node
    """
    authentication_classes = [JWTCookieAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, canvas_id, node_id):
        """Get cached data for a node."""
        try:
            ensure_user_has_customer = get_ensure_user_has_customer()
            customer = ensure_user_has_customer(request.user)
            
            cache_manager = get_node_cache_manager(customer)
            cached_data = cache_manager.get_cache(int(canvas_id), node_id)
            
            if cached_data:
                return Response({
                    'success': True,
                    'from_cache': True,
                    **cached_data
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'from_cache': False,
                    'message': 'No valid cache found for this node'
                }, status=status.HTTP_404_NOT_FOUND)
                
        except Exception as e:
            logger.error(f"Error getting node cache: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, canvas_id, node_id):
        """Save node data to cache."""
        try:
            ensure_user_has_customer = get_ensure_user_has_customer()
            customer = ensure_user_has_customer(request.user)
            
            node_type = request.data.get('node_type', 'unknown')
            rows = request.data.get('rows', [])
            columns = request.data.get('columns', [])
            config = request.data.get('config', {})
            source_node_ids = request.data.get('source_node_ids', [])
            
            cache_manager = get_node_cache_manager(customer)
            success = cache_manager.save_cache(
                canvas_id=int(canvas_id),
                node_id=node_id,
                node_type=node_type,
                rows=rows,
                columns=columns,
                config=config,
                source_node_ids=source_node_ids
            )
            
            if success:
                return Response({
                    'success': True,
                    'message': f'Cached {len(rows)} rows for node {node_id}'
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to save cache'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Error saving node cache: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, canvas_id, node_id=None):
        """Invalidate cache for a node or entire canvas."""
        try:
            ensure_user_has_customer = get_ensure_user_has_customer()
            customer = ensure_user_has_customer(request.user)
            
            cache_manager = get_node_cache_manager(customer)
            cache_manager.invalidate_cache(int(canvas_id), node_id)
            
            return Response({
                'success': True,
                'message': f'Cache invalidated for canvas {canvas_id}' + (f', node {node_id}' if node_id else '')
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error invalidating node cache: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NodeCacheStatsView(APIView):
    """
    API view for cache statistics.
    
    GET /api/node-cache/stats/
        Get all cache statistics
        
    GET /api/node-cache/stats/<canvas_id>/
        Get cache statistics for a specific canvas
    """
    authentication_classes = [JWTCookieAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, canvas_id=None):
        """Get cache statistics."""
        try:
            ensure_user_has_customer = get_ensure_user_has_customer()
            customer = ensure_user_has_customer(request.user)
            
            cache_manager = get_node_cache_manager(customer)
            stats = cache_manager.get_cache_stats(int(canvas_id) if canvas_id else None)
            
            # Convert datetime objects to strings for JSON serialization
            for cache in stats.get('caches', []):
                for key in ['created_on', 'last_accessed']:
                    if key in cache and cache[key]:
                        cache[key] = cache[key].isoformat() if hasattr(cache[key], 'isoformat') else str(cache[key])
            
            return Response(stats, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NodeCacheCleanupView(APIView):
    """
    API view for cache cleanup operations.
    
    POST /api/node-cache/cleanup/
        Clean up old caches (default: older than 7 days)
    """
    authentication_classes = [JWTCookieAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Clean up old caches."""
        try:
            ensure_user_has_customer = get_ensure_user_has_customer()
            customer = ensure_user_has_customer(request.user)
            
            days_old = int(request.data.get('days_old', 7))
            
            cache_manager = get_node_cache_manager(customer)
            cache_manager.cleanup_old_caches(days_old)
            
            return Response({
                'success': True,
                'message': f'Cleaned up caches older than {days_old} days'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error cleaning up caches: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
