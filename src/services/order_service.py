import asyncio
import uuid
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.models.database import Order, OrderItem, InventoryItem
from src.models.schemas import OrderCreate
import logging

logger = logging.getLogger(__name__)

class OrderProcessingService:
    """
    Order processing service with race condition bug.
    Multiple concurrent orders for the same item can cause overselling.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    async def process_order(self, order_data: OrderCreate) -> Order:
        """
        Process a new order - THIS HAS A RACE CONDITION BUG!
        
        The bug: Between checking inventory and updating it, another
        concurrent request can also check the same inventory and both
        will see the same available quantity, leading to overselling.
        """
        logger.info(f"Processing order for {order_data.customer_email}")
        
        # Generate order number
        order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        
        # Step 1: Check inventory availability (NON-ATOMIC)
        total_amount = 0.0
        order_items_data = []
        
        for item_request in order_data.items:
            # This query doesn't lock the row - RACE CONDITION!
            inventory_item = self.db.query(InventoryItem).filter(
                InventoryItem.id == item_request.inventory_item_id
            ).first()
            
            if not inventory_item:
                raise ValueError(f"Inventory item {item_request.inventory_item_id} not found")
            
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
                "total_price": total_price,
                "inventory_item": inventory_item
            })
        
        # Simulate some processing delay to increase race condition likelihood
        await asyncio.sleep(0.1)
        
        # Step 2: Create order (still not atomic with inventory update)
        order = Order(
            order_number=order_number,
            customer_email=order_data.customer_email,
            status="pending",
            total_amount=total_amount
        )
        self.db.add(order)
        self.db.flush()  # Get the order ID
        
        # Step 3: Create order items and update inventory (NON-ATOMIC)
        for item_data in order_items_data:
            # Create order item
            order_item = OrderItem(
                order_id=order.id,
                inventory_item_id=item_data["inventory_item_id"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                total_price=item_data["total_price"]
            )
            self.db.add(order_item)
            
            # Update inventory - RACE CONDITION HERE!
            # Another concurrent transaction might have already reduced this stock
            inventory_item = item_data["inventory_item"]
            inventory_item.quantity_available -= item_data["quantity"]
            
            # Log the inventory update for debugging
            logger.info(
                f"Updated inventory for {inventory_item.name}: "
                f"new quantity = {inventory_item.quantity_available}"
            )
        
        # Commit all changes
        self.db.commit()
        
        # Update order status
        order.status = "confirmed"
        self.db.commit()
        
        logger.info(f"Order {order_number} processed successfully")
        return order
    
    def get_inventory_status(self) -> List[dict]:
        """Get current inventory status for debugging"""
        items = self.db.query(InventoryItem).all()
        return [
            {
                "id": item.id,
                "product_id": item.product_id,
                "name": item.name,
                "quantity_available": item.quantity_available
            }
            for item in items
        ]