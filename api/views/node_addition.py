"""
Node Addition API endpoints for explicit node insertion methods.
Supports two methods:
1. Edge-based insertion (insert between nodes)
2. Output handle-based addition (add after node)
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from api.authentications import JWTCookieAuthentication
from api.utils.helpers import ensure_user_has_customer
from api.utils.graph_utils import validate_dag
from api.utils.cache_aware_execution import (
    find_downstream_nodes,
)
import logging
import uuid
from typing import List, Dict, Any, Set

logger = logging.getLogger(__name__)


class AddNodeAfterView(APIView):
    """
    API endpoint for adding a node after another node (output handle-based).
    
    POST /api/pipeline/add-node-after/
    Body:
    {
        "canvas_id": 1,
        "new_node": {
            "id": "uuid",
            "type": "filter",
            "config": {...},
            "position": {"x": 100, "y": 200}
        },
        "source_node_id": "node-a-id"
    }
    """
    authentication_classes = [JWTCookieAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Add a node after a source node (output handle-based).
        
        Creates edge: A → X
        If A already has downstream nodes, creates parallel branch:
        A → B
        A → X
        
        Cache behavior:
        - Preserve cache for A and upstream
        - Only new branch (X and downstream) recomputes
        """
        try:
            user = request.user
            customer = ensure_user_has_customer(user)
            
            canvas_id = request.data.get('canvas_id')
            new_node_data = request.data.get('new_node', {})
            source_node_id = request.data.get('source_node_id')  # Node A (parent)
            
            if not canvas_id or not new_node_data or not source_node_id:
                return Response(
                    {"error": "canvas_id, new_node, and source_node_id are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get canvas
            from api.models.canvas import Canvas
            try:
                canvas = Canvas.objects.get(id=canvas_id, customer=customer)
            except Canvas.DoesNotExist:
                return Response(
                    {"error": f"Canvas {canvas_id} not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get current pipeline configuration
            config = canvas.configuration or {}
            nodes = config.get('nodes', [])
            edges = config.get('edges', [])
            
            # Validate that source node exists
            source_node = next((n for n in nodes if n.get('id') == source_node_id), None)
            if not source_node:
                return Response(
                    {"error": f"Source node {source_node_id} not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # ENFORCEMENT: Cannot add Source node after another node
            new_node_type = new_node_data.get('type')
            if new_node_type == 'source':
                return Response(
                    {"error": "Source node can only be added via table drop, not via output handle insertion."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # ENFORCEMENT: Check if Source node already exists (only one Source allowed)
            existing_source_nodes = [n for n in nodes if n.get('data', {}).get('type') == 'source']
            if len(existing_source_nodes) > 0:
                return Response(
                    {"error": "Only one Source node is allowed per pipeline. Source node is always the root."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # ENFORCEMENT: Cannot add Source node via output handle (Source is only via table drop)
            if new_node_type == 'source':
                return Response(
                    {"error": "Source node can only be added via table drop, not via output handle insertion."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate new node ID if not provided
            new_node_id = new_node_data.get('id') or str(uuid.uuid4())
            
            # Validate DAG after addition
            new_nodes = nodes + [{
                'id': new_node_id,
                'data': {
                    'type': new_node_data.get('type', 'filter'),
                    'config': new_node_data.get('config', {}),
                    'label': new_node_data.get('label', f"New {new_node_data.get('type', 'node')}")
                },
                'position': new_node_data.get('position', {'x': 0, 'y': 0})
            }]
            
            # Add edge: A → X (parallel branches allowed)
            new_edges = edges.copy()
            
            # Check if edge already exists (shouldn't happen, but validate)
            existing_edge = next(
                (e for e in edges if e.get('source') == source_node_id and e.get('target') == new_node_id),
                None
            )
            
            if not existing_edge:
                new_edges.append({
                    'id': f"{source_node_id}-{new_node_id}",
                    'source': source_node_id,
                    'target': new_node_id,
                    'sourceHandle': 'output',
                    'targetHandle': 'input'
                })
            
            # Validate DAG
            is_valid, dag_error = validate_dag(new_nodes, new_edges)
            if not is_valid:
                return Response(
                    {"error": f"Invalid DAG after addition: {dag_error}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update canvas configuration
            config['nodes'] = new_nodes
            config['edges'] = new_edges
            canvas.configuration = config
            canvas.save()

            # Persist node details to DB (pipeline_nodes, canvas_edge)
            try:
                from api.utils.canvas_node_sync import sync_configuration_to_db
                sync_configuration_to_db(canvas)
            except Exception as sync_err:
                logger.warning(f"[NODE ADD] Failed to sync nodes to DB: {sync_err}")

            from api.utils.metadata_sync import update_node_metadata_for_canvas
            update_node_metadata_for_canvas(canvas)

            # Cache invalidation: Only invalidate new branch (X and downstream)
            from api.services.checkpoint_cache import CheckpointCacheManager
            checkpoint_mgr = CheckpointCacheManager(customer.cust_db, canvas_id)
            checkpoint_mgr.invalidate_downstream(new_node_id, new_nodes, new_edges)
            
            logger.info(f"Added node {new_node_id} after {source_node_id}")
            logger.info(f"Preserved upstream caches (A and upstream)")
            logger.info(f"Invalidated downstream caches in new branch for node {new_node_id}")
            
            return Response({
                "success": True,
                "node_id": new_node_id,
                "preserved_caches": [source_node_id],  # A's cache is preserved
                "message": "Node added successfully. Downstream caches invalidated in new branch."
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error adding node after: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return Response(
                {"error": f"Failed to add node: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
