"""
Validation-Gated Execution Lifecycle
Enforces strict state management for production-safe ETL orchestration.
"""

from .state_machine import (
    PipelineState,
    validate_pipeline,
    invalidate_validation,
    execute_validated_plan,
    get_pipeline_state,
    can_execute
)

__all__ = [
    "PipelineState",
    "validate_pipeline",
    "invalidate_validation",
    "execute_validated_plan",
    "get_pipeline_state",
    "can_execute"
]
