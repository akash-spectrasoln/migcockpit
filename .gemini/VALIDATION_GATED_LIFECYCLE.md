# Validation-Gated Execution Lifecycle

## Overview

**Production-safe orchestration** with strict state management that enforces:
- ✅ Validate → Freeze Plan → Execute
- ✅ DAG Change → Invalidate Validation
- ✅ Execution Only from Stored Plan
- ✅ No Accidental Re-Planning
- ✅ Deterministic & Drift-Proof

---

## 🎯 Core Safety Invariant (NON-NEGOTIABLE)

Execution of any ETL pipeline is allowed **ONLY** when:

```
pipeline_state == VALIDATED
AND
execution_plan_json IS NOT NULL
AND
plan_hash matches current DAG hash
```

**If any condition fails → execution MUST be rejected. No exceptions.**

---

## 📋 Pipeline States (Finite State Machine)

```
┌─────────┐
│  DRAFT  │ ← DAG edited/created, no valid plan, execution FORBIDDEN
└────┬────┘
     │ validate()
     ▼
┌──────────────┐
│  VALIDATED   │ ← DAG verified, plan frozen, execution ALLOWED
└──────┬───────┘
       │ execute()
       ▼
┌──────────────┐
│   RUNNING    │ ← Executor processing stored plan
└──────┬───────┘
       │
       ├─ success ──→ ┌──────────┐
       │              │ SUCCESS  │ ← Terminal state
       │              └──────────┘
       │
       └─ failure ──→ ┌──────────┐
                      │  FAILED  │ ← Terminal state
                      └──────────┘
```

### State Meanings

| State | Description | Execution Allowed? |
|-------|-------------|-------------------|
| **DRAFT** | DAG edited or created, no valid execution plan | ❌ NO |
| **VALIDATED** | DAG verified, execution plan generated & frozen | ✅ YES |
| **RUNNING** | Executor is processing stored plan | ❌ NO (already running) |
| **SUCCESS** | Terminal state - successful completion | ❌ NO (completed) |
| **FAILED** | Terminal state - execution failed | ❌ NO (failed) |

---

## 🔄 Lifecycle Operations

### 1. VALIDATE Operation (Plan Creation Phase)

**Endpoint**: `POST /validate`

**Steps** (ALL must succeed):

```python
# Step 1: DAG correctness validation
validate_dag(nodes, edges)
# Checks: acyclic, valid JOINs, reachable nodes, valid configs
# Fail → remain in DRAFT

# Step 2: Build deterministic execution plan
execution_plan = build_execution_plan(dag, job_id)
# Follows minimal-staging rules

# Step 3: Compute plan hash
plan_hash = sha256(normalized_execution_plan_json)

# Step 4: Persist validation result
storage.save_validation(
    job_id=job_id,
    state=VALIDATED,
    execution_plan_json=json.dumps(execution_plan),
    plan_hash=plan_hash,
    validated_at=datetime.utcnow()
)
# Execution plan is now IMMUTABLE
```

**Result**: Pipeline state → `VALIDATED`, plan frozen, execution allowed

---

### 2. DAG MUTATION → VALIDATION INVALIDATION (CRITICAL)

**Any change to DAG MUST immediately invalidate validation.**

**DAG mutations include**:
- Node added/removed
- Edge added/removed
- Node configuration changed
- Source/destination parameters changed

**Required system reaction**:

```python
# MUST be called on ANY DAG mutation
invalidate_validation(job_id)

# Which MUST execute:
storage.invalidate_validation(
    job_id=job_id,
    state=DRAFT,
    execution_plan_json=None,
    plan_hash=None,
    validated_at=None
)
```

**This rule is non-bypassable.**

---

### 3. EXECUTE Operation (Runtime Phase)

**Endpoint**: `POST /execute`

**Pre-Execution Guard** (MANDATORY):

```python
# Execution allowed ONLY IF:
can_execute, error = can_execute(job_id, nodes, edges, storage)

if not can_execute:
    return {"error": error, "status": "forbidden"}
    # DO NOT start execution

# Checks:
# 1. pipeline_state == VALIDATED
# 2. execution_plan_json IS NOT NULL
# 3. stored_plan_hash == recomputed_dag_hash
```

**Execution Source of Truth** (CRITICAL):

```python
# Executor MUST NOT rebuild the plan
# It MUST use stored execution_plan_json

metadata = storage.get_pipeline_metadata(job_id)
execution_plan = json.loads(metadata.execution_plan_json)

# Execute using stored plan
result = executor.execute_plan(execution_plan)
```

**Guarantees**:
- ✅ Determinism (same plan every time)
- ✅ Auditability (plan is logged)
- ✅ Replay safety (can retry with exact same plan)

---

### 4. State Transitions During Execution

```python
# When execution starts:
storage.update_state(
    job_id=job_id,
    state=RUNNING,
    started_at=datetime.utcnow()
)

try:
    result = executor.execute_plan(execution_plan)
    
    # On successful completion:
    storage.update_state(
        job_id=job_id,
        state=SUCCESS,
        finished_at=datetime.utcnow()
    )
    
except Exception as e:
    # On failure:
    storage.update_state(
        job_id=job_id,
        state=FAILED,
        finished_at=datetime.utcnow()
    )
    
    # Failure must still ensure:
    # - Staging schema cleanup
    # - Error logging
    # - WebSocket notification
```

---

## 🖥️ UI Enforcement Rules (MANDATORY)

Frontend **MUST** obey backend state.

### Button Enablement Matrix

| State | Validate Button | Execute Button |
|-------|----------------|----------------|
| **DRAFT** | ✅ Enabled | ❌ Disabled |
| **VALIDATED** | ✅ Enabled | ✅ Enabled |
| **RUNNING** | ❌ Disabled | ❌ Disabled |
| **SUCCESS** | ✅ Enabled | ❌ Disabled |
| **FAILED** | ✅ Enabled | ❌ Disabled |

**UI MUST NOT allow execution in DRAFT state.**

---

## 🔒 Determinism & Safety Guarantees

The system **MUST** guarantee:

1. ✅ **Same DAG → Same Plan Hash**
   - Identical DAG produces identical execution plan
   - Plan hash is deterministic

2. ✅ **Execution Always Uses Validated Frozen Plan**
   - Executor never rebuilds plan
   - Stored plan is source of truth

3. ✅ **No Stale Execution After DAG Edits**
   - Any DAG mutation invalidates validation
   - Execution forbidden until re-validation

4. ✅ **Safe Celery Retries Using Stored Plan**
   - Retries use same frozen plan
   - No drift between attempts

5. ✅ **Full Audit Trail**
   - Validation timestamp logged
   - Execution start/end logged
   - Plan hash logged

**Any violation = invalid implementation.**

---

## 🗄️ Required Backend Components

### Persistence Model Fields

```python
class PipelineJob(models.Model):
    job_id = models.CharField(primary_key=True)
    
    # Lifecycle state
    pipeline_state = models.CharField(
        choices=[
            ('draft', 'Draft'),
            ('validated', 'Validated'),
            ('running', 'Running'),
            ('success', 'Success'),
            ('failed', 'Failed')
        ],
        default='draft'
    )
    
    # Execution plan
    execution_plan_json = models.TextField(null=True, blank=True)
    plan_hash = models.CharField(max_length=64, null=True, blank=True)
    
    # Timestamps
    validated_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
```

### Core Service Functions

```python
# 1. Validate pipeline and freeze plan
validate_pipeline(job_id, nodes, edges, config, storage)

# 2. Invalidate validation on DAG mutation
invalidate_validation(job_id, storage)

# 3. Execute using validated frozen plan
execute_validated_plan(job_id, storage, executor)

# 4. Check if execution is allowed
can_execute(job_id, nodes, edges, storage)

# 5. Get current pipeline state
get_pipeline_state(job_id, storage)
```

---

## 📊 Example Workflow

### Scenario: User Creates and Executes Pipeline

```
1. User creates DAG in UI
   → Backend: pipeline_state = DRAFT

2. User clicks "Validate"
   → Backend: validate_pipeline()
   → DAG validated ✓
   → Execution plan generated ✓
   → Plan hash computed ✓
   → Persisted to database ✓
   → pipeline_state = VALIDATED

3. User clicks "Execute"
   → Backend: can_execute() checks
   → State == VALIDATED ✓
   → Plan exists ✓
   → Hash matches ✓
   → execute_validated_plan()
   → pipeline_state = RUNNING
   → Executor uses stored plan (NOT rebuilt)
   → Success
   → pipeline_state = SUCCESS

4. User edits DAG (adds node)
   → Backend: invalidate_validation()
   → pipeline_state = DRAFT
   → execution_plan_json = NULL
   → plan_hash = NULL

5. User clicks "Execute" (without re-validating)
   → Backend: can_execute() checks
   → State == DRAFT ✗
   → Return error: "Must validate first"
   → Execution BLOCKED ✓
```

---

## ✅ Final Compliance Check

Before deploying, verify:

### Question 1: Is execution EVER possible without VALIDATED state?

**Answer**: ❌ **NO**

The `can_execute()` guard explicitly checks `state == VALIDATED`.

### Question 2: Is plan EVER rebuilt during EXECUTE?

**Answer**: ❌ **NO**

The executor uses `stored execution_plan_json`, never calls `build_execution_plan()`.

### Question 3: Can DAG change leave plan still valid?

**Answer**: ❌ **NO**

Any DAG mutation calls `invalidate_validation()`, setting state to DRAFT and clearing plan.

**All answers are NO → Implementation is COMPLIANT ✅**

---

## 🧪 Testing

### Test Cases

1. **Test: Execution blocked in DRAFT state**
   ```python
   assert can_execute(job_id, nodes, edges, storage) == (False, "...")
   ```

2. **Test: Validation creates frozen plan**
   ```python
   result = validate_pipeline(job_id, nodes, edges, config, storage)
   assert result.is_valid == True
   assert result.plan_hash is not None
   ```

3. **Test: DAG mutation invalidates validation**
   ```python
   validate_pipeline(...)  # State = VALIDATED
   invalidate_validation(job_id, storage)
   metadata = get_pipeline_state(job_id, storage)
   assert metadata.state == PipelineState.DRAFT
   assert metadata.execution_plan_json is None
   ```

4. **Test: Execution uses stored plan**
   ```python
   validate_pipeline(...)
   execute_validated_plan(job_id, storage, executor)
   # Verify executor received stored plan, not rebuilt
   ```

5. **Test: Hash mismatch blocks execution**
   ```python
   validate_pipeline(...)
   # Manually corrupt plan hash
   storage._storage[job_id]["plan_hash"] = "invalid"
   assert can_execute(...) == (False, "...")
   ```

---

## 📚 Implementation Files

| File | Purpose |
|------|---------|
| **`lifecycle/__init__.py`** | Package exports |
| **`lifecycle/state_machine.py`** | Core state machine logic |
| **`lifecycle/storage.py`** | Storage interface & in-memory impl |
| **`VALIDATION_GATED_LIFECYCLE.md`** | This documentation |

---

## 🎯 Summary

The Validation-Gated Execution Lifecycle provides:

- ✅ **Strict state management** (finite state machine)
- ✅ **Execution guards** (prevent invalid execution)
- ✅ **Frozen plans** (deterministic, auditable)
- ✅ **DAG mutation detection** (automatic invalidation)
- ✅ **Production safety** (no accidental re-planning)
- ✅ **Drift-proof** (hash verification)

**The system is now production-grade with enterprise-level safety guarantees!** ✅🚀
