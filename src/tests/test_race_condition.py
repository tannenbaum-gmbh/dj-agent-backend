import pytest
import asyncio
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.database import Base, InventoryItem, Order, OrderItem
from src.models.schemas import OrderCreate, OrderItemCreate
from src.services.order_service import OrderProcessingService

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite:///./test.db"

@pytest.fixture
def test_engine():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def test_db(test_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def sample_inventory_item(test_db):
    """Create a sample inventory item for testing"""
    item = InventoryItem(
        product_id="DJ-MIXER-001",
        name="Professional DJ Mixer",
        description="High-quality DJ mixer for professional use",
        price=299.99,
        quantity_available=5  # Only 5 items in stock
    )
    test_db.add(item)
    test_db.commit()
    test_db.refresh(item)
    return item

class TestRaceConditionBug:
    """Test cases to reproduce the race condition bug in order processing"""
    
    @pytest.mark.asyncio
    async def test_single_order_success(self, test_db, sample_inventory_item):
        """Test that a single order works correctly"""
        service = OrderProcessingService(test_db)
        
        order_data = OrderCreate(
            customer_email="customer1@example.com",
            items=[
                OrderItemCreate(
                    inventory_item_id=sample_inventory_item.id,
                    quantity=2
                )
            ]
        )
        
        order = await service.process_order(order_data)
        
        # Check order was created
        assert order.order_number.startswith("ORD-")
        assert order.customer_email == "customer1@example.com"
        assert order.status == "confirmed"
        assert order.total_amount == 599.98  # 2 * 299.99
        
        # Check inventory was reduced
        test_db.refresh(sample_inventory_item)
        assert sample_inventory_item.quantity_available == 3  # 5 - 2 = 3
    
    @pytest.mark.asyncio
    async def test_insufficient_inventory(self, test_db, sample_inventory_item):
        """Test that orders fail when insufficient inventory"""
        service = OrderProcessingService(test_db)
        
        order_data = OrderCreate(
            customer_email="customer1@example.com",
            items=[
                OrderItemCreate(
                    inventory_item_id=sample_inventory_item.id,
                    quantity=10  # More than available (5)
                )
            ]
        )
        
        with pytest.raises(ValueError, match="Insufficient stock"):
            await service.process_order(order_data)
        
        # Check inventory was not changed
        test_db.refresh(sample_inventory_item)
        assert sample_inventory_item.quantity_available == 5
    
    @pytest.mark.asyncio
    async def test_race_condition_overselling(self, test_db, sample_inventory_item):
        """
        Test that demonstrates the race condition bug.
        Two concurrent orders for the same item can cause overselling.
        """
        # Create two services (simulating concurrent requests)
        service1 = OrderProcessingService(test_db)
        service2 = OrderProcessingService(test_db)
        
        # Both orders request 3 items out of 5 available
        # Total requested: 6 items, but only 5 available
        # With race condition, both might succeed
        order_data1 = OrderCreate(
            customer_email="customer1@example.com",
            items=[
                OrderItemCreate(
                    inventory_item_id=sample_inventory_item.id,
                    quantity=3
                )
            ]
        )
        
        order_data2 = OrderCreate(
            customer_email="customer2@example.com",
            items=[
                OrderItemCreate(
                    inventory_item_id=sample_inventory_item.id,
                    quantity=3
                )
            ]
        )
        
        # Execute both orders concurrently
        try:
            order1, order2 = await asyncio.gather(
                service1.process_order(order_data1),
                service2.process_order(order_data2),
                return_exceptions=True
            )
            
            # Check if both orders succeeded (demonstrating the bug)
            successful_orders = 0
            if isinstance(order1, Order):
                successful_orders += 1
            if isinstance(order2, Order):
                successful_orders += 1
            
            # Check final inventory
            test_db.refresh(sample_inventory_item)
            final_quantity = sample_inventory_item.quantity_available
            
            print(f"Successful orders: {successful_orders}")
            print(f"Final inventory quantity: {final_quantity}")
            
            # If both orders succeeded, we have overselling (the bug!)
            if successful_orders == 2:
                # This would mean 6 items were sold but only 5 were available
                # Final quantity should be -1 (oversold by 1)
                assert final_quantity == -1, "Race condition bug: inventory oversold!"
                print("BUG REPRODUCED: Both orders succeeded, causing overselling!")
            else:
                # One order should fail, and inventory should be 2 (5 - 3 = 2)
                assert final_quantity == 2, "Expected one order to fail"
                print("Race condition avoided (this time)")
                
        except Exception as e:
            pytest.fail(f"Unexpected error during race condition test: {e}")
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_orders(self, test_db, sample_inventory_item):
        """
        Test multiple concurrent orders to increase chance of race condition
        """
        # Create 5 concurrent orders, each requesting 2 items
        # Total: 10 items requested, but only 5 available
        orders_data = [
            OrderCreate(
                customer_email=f"customer{i}@example.com",
                items=[
                    OrderItemCreate(
                        inventory_item_id=sample_inventory_item.id,
                        quantity=2
                    )
                ]
            )
            for i in range(1, 6)
        ]
        
        # Create services for concurrent processing
        services = [OrderProcessingService(test_db) for _ in range(5)]
        
        # Execute all orders concurrently
        results = await asyncio.gather(
            *[service.process_order(order_data) for service, order_data in zip(services, orders_data)],
            return_exceptions=True
        )
        
        # Count successful orders
        successful_orders = sum(1 for result in results if isinstance(result, Order))
        
        # Check final inventory
        test_db.refresh(sample_inventory_item)
        final_quantity = sample_inventory_item.quantity_available
        
        print(f"Successful orders: {successful_orders}")
        print(f"Final inventory quantity: {final_quantity}")
        
        # With proper concurrency control, only 2 orders should succeed (2*2 = 4 items)
        # and 1 item should remain
        # With race condition bug, more orders might succeed causing negative inventory
        
        if final_quantity < 0:
            print(f"BUG REPRODUCED: Overselling detected! Final quantity: {final_quantity}")
        elif successful_orders > 2:
            print(f"POTENTIAL BUG: {successful_orders} orders succeeded when only 2 should")
        else:
            print("Race condition avoided in this test run")