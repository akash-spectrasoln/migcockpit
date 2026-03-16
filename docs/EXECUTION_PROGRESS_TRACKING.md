# Real-Time Execution Progress Tracking

## Architecture Overview

This system implements production-grade execution progress tracking for the SQL pushdown ETL pipeline with strict state machine transitions, deterministic progress calculation, and real-time WebSocket emissions.

## Core Principles

### 1. Ephemeral Runtime State

**Execution progress is NOT stored in the database.**

- Lives only in **memory** (ExecutionStateStore)
- Broadcast via **WebSocket** in real-time
- **Auto-expires** after 15 minutes (configurable TTL)

Permanent history belongs only to:
- `MigrationJob.status` (final outcome)
- Logs
- Metrics

### 2. Strict State Machine

Every node follows this state machine:

```
PENDING → RUNNING → SUCCESS
                  → FAILED
```

Invalid transitions are rejected with warnings.

### 3. Deterministic Progress

Pipeline progress is calculated using:

```python
overall_progress = (completed_nodes + sum(running_node_progress)) / total_nodes * 100
```

NOT time-based. NOT arbitrary increments.

## Components

### 1. ExecutionStateStore (`orchestrator/execution_state.py`)

In-memory store for runtime execution state.

**Features:**
- Strict state machine enforcement
- TTL auto-expiry (15 minutes default)
- Background cleanup task
- Thread-safe with async locks
- Deterministic progress calculation

**Key Methods:**
```python
# Initialize execution (all nodes PENDING)
await execution_store.initialize_execution(job_id, node_ids, total_levels)

# Start pipeline (PENDING → RUNNING)
await execution_store.start_pipeline(job_id, current_step)

# Start node (PENDING → RUNNING)
await execution_store.start_node(job_id, node_id, phase)

# Update node progress
await execution_store.update_node_progress(job_id, node_id, phase_progress, overall_progress)

# Complete node (RUNNING → SUCCESS/FAILED)
await execution_store.complete_node(job_id, node_id, success, error)

# Complete pipeline
await execution_store.complete_pipeline(job_id, success, error)

# Mark remaining nodes as SKIPPED on failure
await execution_store.fail_remaining_nodes(job_id)

# Query state (returns None if expired)
state = await execution_store.get_state(job_id)
```

### 2. WebSocketEmitter (`orchestrator/ws_emitter.py`)

Handles all WebSocket event emissions.

**Event Types:**
- `pipeline_started` - Pipeline begins execution
- `node_started` - Node transitions to RUNNING
- `node_progress` - Node progress update
- `node_completed` - Node transitions to SUCCESS
- `node_failed` - Node transitions to FAILED
- `pipeline_progress` - Overall pipeline progress update
- `pipeline_completed` - Pipeline completes successfully
- `pipeline_failed` - Pipeline fails

**Key Methods:**
```python
await ws_emitter.emit_pipeline_started(job_id, state)
await ws_emitter.emit_node_started(job_id, node)
await ws_emitter.emit_node_progress(job_id, node, overall_progress)
await ws_emitter.emit_node_completed(job_id, node, overall_progress)
await ws_emitter.emit_node_failed(job_id, node)
await ws_emitter.emit_pipeline_progress(job_id, state)
await ws_emitter.emit_pipeline_completed(job_id, state)
await ws_emitter.emit_pipeline_failed(job_id, state)
```

### 3. Pushdown Executor Integration (`orchestrator/execute_pipeline_pushdown.py`)

The pushdown executor is fully integrated with state tracking:

**Execution Flow:**
1. **Initialize state** - All nodes set to PENDING
2. **Start pipeline** - Pipeline → RUNNING, emit `pipeline_started`
3. **For each level:**
   - Update pipeline step metadata
   - **For each query/node:**
     - Start node (PENDING → RUNNING), emit `node_started`
     - Execute SQL
     - Complete node (RUNNING → SUCCESS), emit `node_completed`
     - Emit `pipeline_progress`
4. **Complete pipeline** - Pipeline → SUCCESS, emit `pipeline_completed`

**Error Handling:**
- Mark remaining nodes as SKIPPED
- Complete pipeline with error
- Emit `pipeline_failed`
- Cleanup staging schema

### 4. FastAPI Lifecycle (`main.py`)

**Startup:**
```python
@app.on_event("startup")
async def startup_event():
    execution_store = get_execution_store()
    await execution_store.start()  # Start background cleanup task
```

**Shutdown:**
```python
@app.on_event("shutdown")
async def shutdown_event():
    execution_store = get_execution_store()
    await execution_store.stop()  # Stop cleanup task
    
    ws_emitter = get_ws_emitter()
    await ws_emitter.close()  # Close HTTP client
```

### 5. State Query API (`routers/execution_state_routes.py`)

Endpoint for querying current execution state:

```
GET /execution/{job_id}/state
```

Returns:
```json
{
  "job_id": "...",
  "found": true,
  "state": {
    "status": "running",
    "overall_progress": 45.5,
    "current_step": "Level 2/5",
    "completed_nodes": 3,
    "total_nodes": 8,
    "node_progress": [
      {
        "node_id": "node_1",
        "status": "success",
        "overall_progress": 100
      },
      {
        "node_id": "node_2",
        "status": "running",
        "phase": "transform",
        "phase_progress": 60,
        "overall_progress": 60
      }
    ]
  }
}
```

## Node Execution Phases

For multi-step operations, nodes can report phases:

```python
class NodePhase(str, Enum):
    EXTRACT = "extract"
    TRANSFORM = "transform"
    LOAD = "load"
    FINALIZE = "finalize"
```

Example:
```python
# Start extraction phase
await execution_store.start_node(job_id, node_id, phase=NodePhase.EXTRACT)

# Update progress within phase
await execution_store.update_node_progress(
    job_id, node_id,
    phase_progress=50,  # 50% through extraction
    overall_progress=12.5  # 12.5% overall (extraction is 25% of total)
)

# Transition to next phase
await execution_store.update_node_progress(
    job_id, node_id,
    phase=NodePhase.TRANSFORM,
    phase_progress=0,
    overall_progress=25
)
```

## Frontend Integration

### WebSocket Subscription

```typescript
import { wsService } from './services/websocket'

// Subscribe BEFORE starting execution
wsService.subscribeToJobUpdates(jobId, {
  onJoined: () => {
    // Fetch catch-up state if needed
    fetch(`/execution/${jobId}/state`)
      .then(r => r.json())
      .then(data => {
        if (data.found) {
          // Update UI with current state
          updatePipelineState(data.state)
        }
      })
  },
  
  onStatus: (data) => {
    // Update pipeline-level progress
    setPipelineProgress(data.progress)
    setCurrentStep(data.current_step)
  },
  
  onNodeProgress: (data) => {
    // Update node-level progress
    updateNodeState(data.node_id, {
      status: data.status,
      phase: data.phase,
      progress: data.overall_progress
    })
  },
  
  onComplete: (data) => {
    // Pipeline completed successfully
    setPipelineStatus('success')
    setPipelineProgress(100)
  },
  
  onError: (data) => {
    // Pipeline failed
    setPipelineStatus('failed')
    setError(data.error)
  }
})

// Start execution
await fetch('/execute', {
  method: 'POST',
  body: JSON.stringify({ job_id: jobId, ... })
})
```

### State Reset on Execute

```typescript
function handleExecute() {
  // Reset all node states to PENDING
  nodes.forEach(node => {
    node.status = 'pending'
    node.progress = 0
  })
  
  // Show pipeline running banner
  setPipelineStatus('running')
  setPipelineProgress(0)
  
  // Subscribe to WebSocket
  wsService.subscribeToJobUpdates(jobId, callbacks)
  
  // Start execution
  executeP ipeline(jobId)
}
```

## TTL and Auto-Expiry

Execution states automatically expire after completion:

- **Default TTL:** 15 minutes
- **Cleanup frequency:** Every 60 seconds
- **After expiry:** State returns `None`, UI shows no progress

This matches professional ETL tools (Airflow, Prefect, Dagster).

## Success Criteria

✅ **Entire flow starts in RUNNING state**
✅ **Each node shows PENDING → RUNNING → SUCCESS accurately**
✅ **Nested phases reflected in progress %**
✅ **Overall pipeline % deterministic**
✅ **No execution ticks stored permanently**
✅ **Status auto-disappears after TTL**
✅ **Works across refresh via WebSocket catch-up**
✅ **Matches behavior of professional ETL orchestrators**

## Testing

### Unit Tests

```python
import pytest
from orchestrator.execution_state import ExecutionStateStore, NodeStatus, PipelineStatus

@pytest.mark.asyncio
async def test_state_machine_transitions():
    store = ExecutionStateStore(ttl_minutes=1)
    await store.start()
    
    # Initialize
    await store.initialize_execution("job1", ["node1", "node2"])
    state = await store.get_state("job1")
    assert state.status == PipelineStatus.PENDING
    assert state.nodes["node1"].status == NodeStatus.PENDING
    
    # Start pipeline
    await store.start_pipeline("job1")
    state = await store.get_state("job1")
    assert state.status == PipelineStatus.RUNNING
    
    # Start node
    await store.start_node("job1", "node1")
    state = await store.get_state("job1")
    assert state.nodes["node1"].status == NodeStatus.RUNNING
    
    # Complete node
    await store.complete_node("job1", "node1", success=True)
    state = await store.get_state("job1")
    assert state.nodes["node1"].status == NodeStatus.SUCCESS
    assert state.completed_nodes == 1
    
    await store.stop()
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_full_pipeline_execution():
    # Test complete execution flow with WebSocket emissions
    # Verify state transitions
    # Verify progress calculation
    # Verify TTL expiry
    pass
```

## Monitoring

### Logs

All state transitions are logged:

```
INFO: Initialized execution state for job abc123: 5 nodes
INFO: Pipeline abc123 started
INFO: Node node_1 started (phase: transform)
INFO: Node node_1 completed: success (pipeline: 20.0%)
INFO: Pipeline abc123 completed: success
INFO: Expired execution state for job abc123
```

### Metrics

Key metrics to monitor:

- Active executions count
- Average execution duration
- Node success/failure rates
- WebSocket emission latency
- State store memory usage

## Production Considerations

### Scaling

For multi-worker deployments, replace in-memory store with Redis:

```python
class RedisExecutionStateStore(ExecutionStateStore):
    def __init__(self, redis_url: str, ttl_minutes: int = 15):
        self.redis = redis.from_url(redis_url)
        self.ttl_seconds = ttl_minutes * 60
    
    async def initialize_execution(self, job_id, node_ids, total_levels):
        # Store in Redis with TTL
        state = PipelineExecutionState(...)
        await self.redis.setex(
            f"execution:{job_id}",
            self.ttl_seconds,
            json.dumps(state.to_dict())
        )
```

### High Availability

- Use Redis Sentinel or Cluster for state store
- Implement WebSocket reconnection logic
- Add state catch-up on reconnect
- Implement idempotent event handling

### Performance

- Batch WebSocket emissions for high-frequency updates
- Use connection pooling for WebSocket service
- Implement rate limiting for state queries
- Monitor memory usage and adjust TTL

## Migration from Old System

1. **Keep old progress tracking** for backward compatibility
2. **Run both systems in parallel** during migration
3. **Gradually migrate frontend** to use new WebSocket events
4. **Deprecate old system** after validation
5. **Remove old code** after full migration

## References

- [Airflow Task Instance States](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/tasks.html#task-instances)
- [Prefect Flow Run States](https://docs.prefect.io/concepts/states/)
- [Dagster Run Status](https://docs.dagster.io/concepts/ops-jobs-graphs/job-execution#run-status)
