# Race Condition Fix Documentation

## Problem Description

The order processing pipeline had a race condition that allowed inventory overselling when multiple concurrent orders were processed for the same items.

### The Bug

In the original implementation (`src/services/order_service.py`):

1. **Non-atomic check-and-update**: Orders would check inventory availability and update stock in separate operations
2. **Race condition window**: Between the inventory check and update, another concurrent request could also check the same inventory
3. **Overselling result**: Both requests would see sufficient stock and both would succeed, causing negative inventory

```python
# BUGGY CODE EXAMPLE:
inventory_item = db.query(InventoryItem).filter(...).first()  # Check stock
if inventory_item.quantity_available >= requested_quantity:    # Race condition here!
    # ... process order ...
    inventory_item.quantity_available -= requested_quantity    # Update stock
```

## The Fix

Implemented optimistic concurrency control in `src/services/order_service_fixed.py`:

### 1. Version-based Optimistic Locking

- Added `version` column to `InventoryItem` model for conflict detection
- Each inventory update increments the version number  
- Updates only succeed if the version hasn't changed since read

```python
# FIXED CODE EXAMPLE:
# Read with version snapshot
inventory_item = db.query(InventoryItem).filter(...).first()
original_version = inventory_item.version

# Later, atomic update with version check
update_count = db.execute(text("""
    UPDATE inventory_items 
    SET quantity_available = :new_quantity, version = :new_version
    WHERE id = :item_id AND version = :expected_version
"""), {...})

if update_count == 0:
    raise ConcurrencyConflictError("Item was modified by another transaction")
```

### 2. Retry Mechanism

- Detects concurrency conflicts and retries up to 3 times
- Uses exponential backoff to reduce contention
- Fails gracefully after max retries

### 3. Database-level Locks (Production)

For production PostgreSQL deployments, the service also supports row-level locking:

```python
inventory_item = db.query(InventoryItem).filter(...).with_for_update().first()
```

## Test Results

### Before Fix (Demonstrating the Bug)

```
=== TESTING BUGGY VERSION ===
- Successful orders: 2 (both succeeded - overselling!)
- Final inventory: -1 (negative - oversold by 1 item)
```

### After Fix (Problem Resolved)

```
=== TESTING FIXED VERSION ===  
- Successful orders: 1 (only one succeeded)
- Final inventory: 1 (positive - no overselling)
✓ Fixed version successfully prevents overselling!
```

## Running the Tests

### Test the Race Condition Bug
```bash
python -m pytest src/tests/test_race_condition.py -v -s
```

### Test the Fix
```bash
python -m pytest src/tests/test_race_condition_fixed.py -v -s
```

### Test API Integration
```bash
python -m pytest src/tests/test_integration.py -v -s
```

### Compare Buggy vs Fixed
```bash
python -m pytest src/tests/test_race_condition_fixed.py::TestComparisonBuggyVsFixed -v -s
```

## Implementation Details

### Files Modified

1. **`src/models/database.py`**: Added `version` column for optimistic locking
2. **`src/services/order_service_fixed.py`**: New service with concurrency fixes
3. **`src/api/routes/orders.py`**: Updated to use fixed service
4. **`src/api/routes/inventory.py`**: Updated to use fixed service

### Key Components

- **ConcurrencyConflictError**: Custom exception for detected conflicts
- **Retry logic**: Handles temporary conflicts with exponential backoff
- **Version checking**: Ensures atomic updates with conflict detection
- **Transaction management**: Proper rollback on errors

## Production Considerations

### PostgreSQL Deployment
- Use `SELECT FOR UPDATE` for row-level locking
- Configure appropriate isolation levels
- Monitor lock contention and deadlocks

### Redis Distributed Locks (Optional)
```python
service = OrderProcessingServiceWithRedis(db, redis_client)
order = await service.process_order_with_redis_lock(order_data)
```

### Monitoring
- Track concurrency conflict rates
- Monitor retry attempts
- Set up alerts for excessive conflicts

## Performance Impact

- **Minimal overhead**: Version checking adds minimal database load
- **Retry cost**: Failed attempts require retries but prevent data corruption  
- **Better reliability**: Prevents inventory discrepancies and customer issues

The fix prioritizes data consistency over marginal performance gains from unchecked concurrent access.