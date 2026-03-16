# Filter Pushdown: Calculated Columns - Quick Reference

## Question: What if the filter is on a calculated column?

**Answer**: It depends on the **type** of calculation and where it's computed.

---

## Decision Tree

```
Is the filter on a calculated column?
│
├─ YES → What type of calculation?
│   │
│   ├─ Simple expression (col1 + col2, col1 * col2, etc.)
│   │   └─ ✅ CAN PUSH by substituting the expression
│   │       Example: WHERE total_price > 1000
│   │       Becomes: WHERE (quantity * unit_price) > 1000
│   │
│   ├─ Expression using columns from multiple JOINed tables
│   │   └─ ⚠️ PARTIAL PUSH - can push to after JOIN, not to source
│   │       Example: WHERE profit > 100 (profit = revenue - cost)
│   │       Push to: SELECT * FROM (JOIN...) WHERE (revenue - cost) > 100
│   │
│   ├─ Aggregate function (SUM, AVG, COUNT, etc.)
│   │   └─ ❌ CANNOT PUSH - must use HAVING clause
│   │       Example: WHERE total_sales > 10000 (total_sales = SUM(amount))
│   │       Must use: HAVING SUM(amount) > 10000
│   │
│   └─ Window function (ROW_NUMBER, RANK, etc.)
│       └─ ❌ CANNOT PUSH - must filter after window computation
│           Example: WHERE row_num = 1 (row_num = ROW_NUMBER() OVER ...)
│           Must stay after window function
│
└─ NO → Standard column filter
    └─ ✅ CAN PUSH to source (if column exists there)
```

---

## Examples

### ✅ Example 1: Simple Calculated Column (PUSHABLE)

**Pipeline:**
```
Source(orders) → Projection(total = qty * price) → Filter(total > 1000)
```

**Without Pushdown (Slow):**
```sql
-- Step 1: Load all orders
CREATE TABLE staging.source AS SELECT * FROM orders;

-- Step 2: Add calculated column
CREATE TABLE staging.projection AS 
SELECT *, quantity * unit_price AS total_price 
FROM staging.source;

-- Step 3: Filter (processes ALL rows first)
CREATE TABLE staging.filter AS
SELECT * FROM staging.projection WHERE total_price > 1000;
```

**With Pushdown (Fast):**
```sql
-- Step 1: Load filtered orders with calculation
CREATE TABLE staging.source AS 
SELECT *, quantity * unit_price AS total_price
FROM orders 
WHERE (quantity * unit_price) > 1000;  -- ← Filter pushed!

-- Step 2 & 3: Eliminated (already filtered)
```

**Performance Gain:** If only 1% of orders match, we process 1% of data instead of 100%.

---

### ⚠️ Example 2: Cross-Table Calculation (PARTIAL PUSH)

**Pipeline:**
```
Source(orders) → Join(products) → Projection(profit = revenue - cost) → Filter(profit > 100)
```

**Without Pushdown:**
```sql
-- Step 1: Join all rows
CREATE TABLE staging.join AS
SELECT l.*, r.* FROM orders l JOIN products r ON ...;

-- Step 2: Add calculated column
CREATE TABLE staging.projection AS
SELECT *, l.revenue - r.cost AS profit FROM staging.join;

-- Step 3: Filter
CREATE TABLE staging.filter AS
SELECT * FROM staging.projection WHERE profit > 100;
```

**With Partial Pushdown:**
```sql
-- Step 1: Join all rows
CREATE TABLE staging.join AS
SELECT l.*, r.*, l.revenue - r.cost AS profit  -- Calculate during JOIN
FROM orders l JOIN products r ON ...
WHERE (l.revenue - r.cost) > 100;  -- ← Filter pushed to JOIN output

-- Steps 2 & 3: Eliminated
```

**Why not push to source?** Because `profit` requires columns from BOTH tables.

---

### ❌ Example 3: Aggregate Calculation (CANNOT PUSH)

**Pipeline:**
```
Source(orders) → GroupBy(customer_id, total = SUM(amount)) → Filter(total > 10000)
```

**Wrong Approach:**
```sql
-- ❌ INVALID: Cannot use aggregate in WHERE
SELECT customer_id, SUM(amount) AS total_sales
FROM orders
WHERE SUM(amount) > 10000  -- ERROR: Aggregates not allowed in WHERE
GROUP BY customer_id;
```

**Correct Approach:**
```sql
-- ✅ VALID: Use HAVING clause
SELECT customer_id, SUM(amount) AS total_sales
FROM orders
GROUP BY customer_id
HAVING SUM(amount) > 10000;  -- Correct: Filter aggregates with HAVING
```

**Why?** SQL evaluates in this order:
1. FROM (source)
2. WHERE (filter rows)
3. GROUP BY (aggregate)
4. HAVING (filter aggregates)
5. SELECT (project columns)

Aggregates don't exist until step 3, so WHERE (step 2) can't reference them.

---

## Implementation Status

| Feature | Status | File |
|---------|--------|------|
| **Simple expression pushdown** | 📝 Designed | `calculated_column_pushdown.py` |
| **Cross-table detection** | 📝 Designed | `calculated_column_pushdown.py` |
| **Aggregate HAVING conversion** | ⏳ Not implemented | - |
| **Window function detection** | ⏳ Not implemented | - |
| **Integration with planner** | ⏳ Not implemented | - |

---

## Key Takeaways

1. **Simple calculations CAN be pushed** by substituting the expression
2. **Cross-table calculations** can only be pushed to the JOIN output, not the source
3. **Aggregates** require HAVING, not WHERE (different SQL clause)
4. **Window functions** cannot be pushed at all (must compute first, filter second)

---

## Recommendation

For **immediate performance gains**:
1. Place filters BEFORE expensive operations (JOINs, aggregates) when possible
2. For calculated columns, manually add the filter expression to the source query
3. For aggregates, use HAVING instead of a separate Filter node

For **long-term solution**:
- Implement the calculated column pushdown analyzer
- Automatically detect and rewrite filter conditions
- Estimated effort: 1-2 weeks
