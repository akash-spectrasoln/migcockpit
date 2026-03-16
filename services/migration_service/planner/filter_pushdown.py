"""
Filter Pushdown Prototype - Simple Case
Handles pushing filters down to source nodes when column names match exactly.
"""

from typing import Dict, List, Any, Set, Optional
from collections import defaultdict


def analyze_simple_filter_pushdown(
    nodes: Dict[str, Any],
    edges: List[Dict[str, Any]]
) -> Dict[str, List[Dict]]:
    """
    Analyze which filters can be pushed down to source nodes.
    
    Simple heuristic:
    - If a filter is directly downstream of a source (no JOIN in between)
    - And the column name exists in the source
    - Then push the filter to the source
    
    Returns:
        {source_node_id: [filter_conditions]}
    """
    # Build adjacency
    forward_adj = defaultdict(list)
    reverse_adj = defaultdict(list)
    for edge in edges:
        forward_adj[edge["source"]].append(edge["target"])
        reverse_adj[edge["target"]].append(edge["source"])
    
    pushed_filters = defaultdict(list)
    
    # Find all filter nodes
    for node_id, node in nodes.items():
        node_type = node.get("type") or node.get("data", {}).get("type")
        
        if node_type != "filter":
            continue
        
        config = node.get("data", {}).get("config", {})
        conditions = config.get("conditions", [])
        
        if not conditions:
            continue
        
        # Trace back to find source nodes
        source_nodes = _find_upstream_sources(node_id, nodes, reverse_adj, forward_adj)
        
        # For each condition, try to push to a source
        for cond in conditions:
            column = cond.get("column")
            if not column:
                continue
            
            # Try to find a source that has this column
            for source_id in source_nodes:
                source_config = nodes[source_id].get("data", {}).get("config", {})
                source_columns = source_config.get("columns", [])
                
                # Check if column exists in source
                if any(col.get("name") == column for col in source_columns):
                    pushed_filters[source_id].append(cond)
                    break
    
    return dict(pushed_filters)


def _find_upstream_sources(
    node_id: str,
    nodes: Dict[str, Any],
    reverse_adj: Dict[str, List[str]],
    forward_adj: Dict[str, List[str]],
    visited: Optional[Set[str]] = None
) -> List[str]:
    """
    Find all source nodes upstream of the given node.
    Stops at JOIN nodes (doesn't traverse through them).
    """
    if visited is None:
        visited = set()
    
    if node_id in visited:
        return []
    
    visited.add(node_id)
    
    node_type = nodes[node_id].get("type") or nodes[node_id].get("data", {}).get("type")
    
    # If this is a source, return it
    if node_type == "source":
        return [node_id]
    
    # If this is a JOIN, stop (don't push through JOINs in simple version)
    if node_type == "join":
        return []
    
    # Otherwise, recurse to parents
    sources = []
    for parent_id in reverse_adj.get(node_id, []):
        sources.extend(_find_upstream_sources(parent_id, nodes, reverse_adj, forward_adj, visited))
    
    return sources


def inject_filter_into_source_sql(source_sql: str, conditions: List[Dict]) -> str:
    """
    Inject WHERE clause into source SELECT statement.
    
    Args:
        source_sql: Original source SQL (e.g., 'SELECT * FROM "public"."table"')
        conditions: Filter conditions to inject
        
    Returns:
        Modified SQL with WHERE clause
    """
    if not conditions:
        return source_sql
    
    # Build WHERE clause
    where_parts = []
    for cond in conditions:
        column = cond.get("column")
        operator = cond.get("operator", "=")
        value = cond.get("value")
        
        if not column:
            continue
        
        # Format value
        if isinstance(value, str):
            value_str = f"'{value}'"
        elif value is None:
            value_str = "NULL"
        else:
            value_str = str(value)
        
        where_parts.append(f'"{column}" {operator} {value_str}')
    
    if not where_parts:
        return source_sql
    
    where_clause = " AND ".join(where_parts)
    
    # Wrap source SQL and add WHERE
    return f"""SELECT * FROM (
    {source_sql}
) src
WHERE {where_clause}"""


# Example usage in sql_compiler.py:
"""
def _compile_source_node_with_pushdown(node, nodes, edges, config, pushed_filters=None):
    # ... existing source compilation logic ...
    base_sql = _compile_source_node(node, nodes, edges, config)
    
    # Inject pushed-down filters
    if pushed_filters and node_id in pushed_filters:
        base_sql = inject_filter_into_source_sql(base_sql, pushed_filters[node_id])
    
    return base_sql
"""
