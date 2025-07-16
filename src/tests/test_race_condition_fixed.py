import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.database import Base, InventoryItem, Order, OrderItem
from src.models.schemas import OrderCreate, OrderItemCreate
from src.services.order_service_fixed import OrderProcessingServiceFixed, OrderProcessingServiceWithRedis

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite:///./test_fixed.db"

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
        product_id="DJ-MIXER-002",
        name="Professional DJ Mixer Fixed",
        description="High-quality DJ mixer for professional use",
        price=299.99,
        quantity_available=5  # Only 5 items in stock
    )
    test_db.add(item)
    test_db.commit()
    test_db.refresh(item)
    return item

class TestFixedOrderProcessing:
    """Test cases to verify the race condition fix"""
    
    @pytest.mark.asyncio
    async def test_single_order_success_fixed(self, test_db, sample_inventory_item):
        """Test that a single order works correctly with the fixed service"""
        service = OrderProcessingServiceFixed(test_db)
        
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
    async def test_race_condition_prevented(self, test_db, sample_inventory_item):
        """
        Test that the fix prevents race condition overselling.
        Two concurrent orders for the same item should not cause overselling.
        """
        # Create two services (simulating concurrent requests)
        service1 = OrderProcessingServiceFixed(test_db)
        service2 = OrderProcessingServiceFixed(test_db)
        
        # Both orders request 3 items out of 5 available
        # Total requested: 6 items, but only 5 available
        # With the fix, only one should succeed
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
        results = await asyncio.gather(
            service1.process_order(order_data1),
            service2.process_order(order_data2),
            return_exceptions=True
        )
        
        # Count successful orders and errors
        successful_orders = sum(1 for result in results if isinstance(result, Order))
        errors = [result for result in results if isinstance(result, Exception)]
        
        # Check final inventory
        test_db.refresh(sample_inventory_item)
        final_quantity = sample_inventory_item.quantity_available
        
        print(f"Successful orders: {successful_orders}")
        print(f"Errors: {len(errors)}")
        print(f"Final inventory quantity: {final_quantity}")
        
        # With the fix, only one order should succeed
        assert successful_orders == 1, f"Expected 1 successful order, got {successful_orders}"
        assert len(errors) == 1, f"Expected 1 error, got {len(errors)}"
        
        # Final inventory should be 2 (5 - 3 = 2), not negative
        assert final_quantity == 2, f"Expected final quantity 2, got {final_quantity}"
        
        # Check that the error is about insufficient stock
        error_messages = [str(error) for error in errors]
        assert any("Insufficient stock" in msg for msg in error_messages), \
            f"Expected 'Insufficient stock' error, got: {error_messages}"
        
        print("SUCCESS: Race condition prevented! No overselling occurred.")
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_orders_fixed(self, test_db, sample_inventory_item):
        """
        Test multiple concurrent orders with the fix.
        Should prevent overselling even with many concurrent requests.
        """
        # Create 5 concurrent orders, each requesting 2 items
        # Total: 10 items requested, but only 5 available
        # With the fix, only 2 orders should succeed (2*2 = 4 items)
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
        services = [OrderProcessingServiceFixed(test_db) for _ in range(5)]
        
        # Execute all orders concurrently
        results = await asyncio.gather(
            *[service.process_order(order_data) for service, order_data in zip(services, orders_data)],
            return_exceptions=True
        )
        
        # Count successful orders and errors
        successful_orders = sum(1 for result in results if isinstance(result, Order))
        errors = [result for result in results if isinstance(result, Exception)]
        
        # Check final inventory
        test_db.refresh(sample_inventory_item)
        final_quantity = sample_inventory_item.quantity_available
        
        print(f"Successful orders: {successful_orders}")
        print(f"Errors: {len(errors)}")
        print(f"Final inventory quantity: {final_quantity}")
        
        # With proper concurrency control, only 2 orders should succeed
        # 2 orders * 2 items each = 4 items sold, 1 item remaining
        assert successful_orders <= 2, f"Expected at most 2 successful orders, got {successful_orders}"
        assert final_quantity >= 1, f"Expected final quantity >= 1, got {final_quantity}"
        assert final_quantity >= 0, f"No overselling should occur, got {final_quantity}"
        
        # All errors should be about insufficient stock
        error_messages = [str(error) for error in errors]
        for msg in error_messages:
            assert "Insufficient stock" in msg, f"Unexpected error: {msg}"
        
        print("SUCCESS: Multiple concurrent orders handled correctly with no overselling!")
    
    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, test_db, sample_inventory_item):
        """
        Test that transactions are properly rolled back on errors,
        ensuring inventory is not corrupted.
        """
        service = OrderProcessingServiceFixed(test_db)
        
        # Create an order that should fail (non-existent inventory item)
        order_data = OrderCreate(
            customer_email="customer1@example.com",
            items=[
                OrderItemCreate(
                    inventory_item_id=sample_inventory_item.id,
                    quantity=2
                ),
                OrderItemCreate(
                    inventory_item_id=99999,  # Non-existent item
                    quantity=1
                )
            ]
        )
        
        # Store original inventory
        original_quantity = sample_inventory_item.quantity_available
        
        # This should fail due to non-existent item
        with pytest.raises(ValueError, match="not found"):
            await service.process_order(order_data)
        
        # Check that inventory was not changed (transaction rollback)
        test_db.refresh(sample_inventory_item)
        assert sample_inventory_item.quantity_available == original_quantity
        
        # Check that no order was created
        orders = test_db.query(Order).all()
        assert len(orders) == 0
        
        print("SUCCESS: Transaction properly rolled back on error!")


class TestComparisonBuggyVsFixed:
    """Compare the buggy and fixed versions side by side"""
    
    @pytest.mark.asyncio
    async def test_comparison_demonstration(self, test_db):
        """
        Demonstrate the difference between buggy and fixed versions.
        Create identical scenarios and show the different outcomes.
        """
        from src.services.order_service import OrderProcessingService as BuggyService
        
        # Create two identical inventory items
        item1 = InventoryItem(
            product_id="DJ-MIXER-BUGGY",
            name="DJ Mixer for Buggy Test",
            price=100.0,
            quantity_available=3
        )
        item2 = InventoryItem(
            product_id="DJ-MIXER-FIXED",
            name="DJ Mixer for Fixed Test",
            price=100.0,
            quantity_available=3
        )
        test_db.add_all([item1, item2])
        test_db.commit()
        test_db.refresh(item1)
        test_db.refresh(item2)
        
        # Create identical order requests
        order_data1 = OrderCreate(
            customer_email="test1@example.com",
            items=[OrderItemCreate(inventory_item_id=item1.id, quantity=2)]
        )
        order_data2 = OrderCreate(
            customer_email="test2@example.com",
            items=[OrderItemCreate(inventory_item_id=item1.id, quantity=2)]
        )
        
        order_data3 = OrderCreate(
            customer_email="test3@example.com",
            items=[OrderItemCreate(inventory_item_id=item2.id, quantity=2)]
        )
        order_data4 = OrderCreate(
            customer_email="test4@example.com",
            items=[OrderItemCreate(inventory_item_id=item2.id, quantity=2)]
        )
        
        # Test buggy version
        print("\n=== TESTING BUGGY VERSION ===")
        buggy_service1 = BuggyService(test_db)
        buggy_service2 = BuggyService(test_db)
        
        buggy_results = await asyncio.gather(
            buggy_service1.process_order(order_data1),
            buggy_service2.process_order(order_data2),
            return_exceptions=True
        )
        
        test_db.refresh(item1)
        print(f"Buggy version - Successful orders: {sum(1 for r in buggy_results if isinstance(r, Order))}")
        print(f"Buggy version - Final inventory: {item1.quantity_available}")
        
        # Test fixed version
        print("\n=== TESTING FIXED VERSION ===")
        fixed_service1 = OrderProcessingServiceFixed(test_db)
        fixed_service2 = OrderProcessingServiceFixed(test_db)
        
        fixed_results = await asyncio.gather(
            fixed_service1.process_order(order_data3),
            fixed_service2.process_order(order_data4),
            return_exceptions=True
        )
        
        test_db.refresh(item2)
        print(f"Fixed version - Successful orders: {sum(1 for r in fixed_results if isinstance(r, Order))}")
        print(f"Fixed version - Final inventory: {item2.quantity_available}")
        
        # Verify the difference
        buggy_final = item1.quantity_available
        fixed_final = item2.quantity_available
        
        print(f"\nCOMPARISON RESULTS:")
        print(f"Buggy version final inventory: {buggy_final} (likely negative - oversold!)")
        print(f"Fixed version final inventory: {fixed_final} (should be non-negative)")
        
        # The fixed version should not oversell
        assert fixed_final >= 0, "Fixed version should not oversell"
        print("✓ Fixed version successfully prevents overselling!")