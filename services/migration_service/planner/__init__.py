"""
SQL Pushdown ETL Planner
Deterministic DAG-based execution with zero Python row processing.
"""

from .validation import validate_pipeline, PipelineValidationError
from .materialization import (
    detect_materialization_points,
    detect_anchor_nodes,
    classify_compute_node,
    should_share_source,
    get_required_fields_for_branch,
    MaterializationPoint,
    MaterializationReason,
    AnchorNode,
)
from .sql_compiler import compile_nested_sql, SQLCompilationError
from .execution_plan import (
    build_execution_plan,
    ExecutionPlan,
    save_execution_plan_to_db,
    get_latest_plan,
    compute_plan_hash,
    deserialize_plan,
)

__all__ = [
    "validate_pipeline",
    "PipelineValidationError",
    "detect_materialization_points",
    "detect_anchor_nodes",
    "MaterializationPoint",
    "MaterializationReason",
    "AnchorNode",
    "classify_compute_node",
    "should_share_source",
    "get_required_fields_for_branch",
    "compile_nested_sql",
    "SQLCompilationError",
    "build_execution_plan",
    "ExecutionPlan",
    "save_execution_plan_to_db",
    "get_latest_plan",
    "compute_plan_hash",
    "deserialize_plan",
]
