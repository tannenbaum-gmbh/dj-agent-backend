import asyncio
import uuid
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import select, text, and_
from src.models.database import Order, OrderItem, InventoryItem
from src.models.schemas import OrderCreate
import logging

logger = logging.getLogger(__name__)

class OrderProcessingServiceFixed:
    """
    Fixed order processing service that prevents race conditions.
    Uses optimistic concurrency control with version numbers for SQLite compatibility.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    async def process_order(self, order_data: OrderCreate) -> Order:
        """
        Process a new order with optimistic concurrency control.
        
        FIX: Uses version numbers to detect concurrent modifications
        and retries if conflicts are detected.
        """
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Processing order for {order_data.customer_email} (attempt {attempt + 1})")
                return await self._process_order_attempt(order_data)
            except ConcurrencyConflictError as e:
                if attempt == max_retries - 1:
                    raise ValueError(f"Unable to process order after {max_retries} attempts: {str(e)}")
                logger.warning(f"Concurrency conflict on attempt {attempt + 1}, retrying...")
                await asyncio.sleep(0.01 * (attempt + 1))  # Exponential backoff
        
        raise ValueError("Failed to process order")
    
    async def _process_order_attempt(self, order_data: OrderCreate) -> Order:
        """Single attempt to process an order"""
        # Generate order number
        order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        
        try:
            # Step 1: Read inventory with current versions
            total_amount = 0.0
            order_items_data = []
            inventory_snapshots = []
            
            for item_request in order_data.items:
                # Read current inventory state
                inventory_item = self.db.query(InventoryItem).filter(
                    InventoryItem.id == item_request.inventory_item_id
                ).first()
                
                if not inventory_item:
                    raise ValueError(f"Inventory item {item_request.inventory_item_id} not found")
                
                # Store snapshot for optimistic locking
                inventory_snapshots.append({
                    'item': inventory_item,
                    'original_version': inventory_item.version,
                    'original_quantity': inventory_item.quantity_available,
                    'requested_quantity': item_request.quantity
                })
                
                # Check if enough stock is available
                if inventory_item.quantity_available < item_request.quantity:
                    raise ValueError(
                        f"Insufficient stock for {inventory_item.name}. "
                        f"Available: {inventory_item.quantity_available}, "
                        f"Requested: {item_request.quantity}"
                    )
                
                # Calculate prices
                unit_price = inventory_item.price
                total_price = unit_price * item_request.quantity
                total_amount += total_price
                
                order_items_data.append({
                    "inventory_item_id": item_request.inventory_item_id,
                    "quantity": item_request.quantity,
                    "unit_price": unit_price,
                    "total_price": total_price
                })
            
            # Simulate some processing delay to increase race condition likelihood
            await asyncio.sleep(0.1)
            
            # Step 2: Create order
            order = Order(
                order_number=order_number,
                customer_email=order_data.customer_email,
                status="pending",
                total_amount=total_amount
            )
            self.db.add(order)
            self.db.flush()  # Get the order ID
            
            # Step 3: Update inventory with optimistic locking
            for i, item_data in enumerate(order_items_data):
                snapshot = inventory_snapshots[i]
                inventory_item = snapshot['item']
                
                # Create order item
                order_item = OrderItem(
                    order_id=order.id,
                    inventory_item_id=item_data["inventory_item_id"],
                    quantity=item_data["quantity"],
                    unit_price=item_data["unit_price"],
                    total_price=item_data["total_price"]
                )
                self.db.add(order_item)
                
                # Optimistic locking: Update only if version hasn't changed
                new_quantity = snapshot['original_quantity'] - snapshot['requested_quantity']
                new_version = snapshot['original_version'] + 1
                
                # Use UPDATE with WHERE clause to check version
                update_count = self.db.execute(
                    text("""
                        UPDATE inventory_items 
                        SET quantity_available = :new_quantity, 
                            version = :new_version,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = :item_id AND version = :expected_version
                    """),
                    {
                        'new_quantity': new_quantity,
                        'new_version': new_version,
                        'item_id': inventory_item.id,
                        'expected_version': snapshot['original_version']
                    }
                ).rowcount
                
                if update_count == 0:
                    # Version changed - another transaction updated this row
                    raise ConcurrencyConflictError(
                        f"Inventory item {inventory_item.name} was modified by another transaction"
                    )
                
                logger.info(
                    f"Updated inventory for {inventory_item.name}: "
                    f"new quantity = {new_quantity} (version {new_version})"
                )
            
            # Commit all changes
            self.db.commit()
            
            # Update order status
            order.status = "confirmed"
            self.db.commit()
            
            logger.info(f"Order {order_number} processed successfully")
            return order
            
        except ConcurrencyConflictError:
            self.db.rollback()
            raise
        except Exception as e:
            # Rollback transaction on any error
            self.db.rollback()
            logger.error(f"Error processing order: {str(e)}")
            raise
    
    def get_inventory_status(self) -> List[dict]:
        """Get current inventory status for debugging"""
        items = self.db.query(InventoryItem).all()
        return [
            {
                "id": item.id,
                "product_id": item.product_id,
                "name": item.name,
                "quantity_available": item.quantity_available,
                "version": item.version
            }
            for item in items
        ]


class ConcurrencyConflictError(Exception):
    """Raised when a concurrency conflict is detected"""
    pass


class OrderProcessingServiceWithRedis:
    """
    Alternative implementation using Redis distributed locks
    for additional protection in distributed systems.
    """
    
    def __init__(self, db: Session, redis_client=None):
        self.db = db
        self.redis_client = redis_client
    
    async def process_order_with_redis_lock(self, order_data: OrderCreate) -> Order:
        """
        Process order with Redis distributed lock for extra protection.
        This is useful in distributed systems where database locks might not be sufficient.
        """
        if not self.redis_client:
            # Fallback to database-only locking
            service = OrderProcessingServiceFixed(self.db)
            return await service.process_order(order_data)
        
        logger.info(f"Processing order with Redis lock for {order_data.customer_email}")
        
        # Generate locks for each inventory item
        lock_keys = [f"inventory_lock:{item.inventory_item_id}" for item in order_data.items]
        
        # Try to acquire all locks
        locks_acquired = []
        try:
            for lock_key in lock_keys:
                # Try to acquire lock with 30 second timeout
                if self.redis_client.set(lock_key, "locked", nx=True, ex=30):
                    locks_acquired.append(lock_key)
                else:
                    # Failed to acquire lock - another process is updating this inventory
                    raise ValueError(f"Another order is currently processing inventory item. Please try again.")
            
            # All locks acquired, proceed with optimistic locking as well
            service = OrderProcessingServiceFixed(self.db)
            order = await service.process_order(order_data)
            
            return order
            
        finally:
            # Release all acquired locks
            for lock_key in locks_acquired:
                self.redis_client.delete(lock_key)