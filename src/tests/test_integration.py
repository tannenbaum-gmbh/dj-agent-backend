import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.database import Base, InventoryItem
from src.core.database import get_db
from main import app

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite:///./test_integration.db"

@pytest.fixture
def test_engine():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def test_db(test_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    yield SessionLocal()
    del app.dependency_overrides[get_db]

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def sample_inventory(test_db):
    """Create sample inventory items"""
    items = [
        InventoryItem(
            product_id="DJ-001",
            name="Professional DJ Mixer",
            description="High-quality mixer",
            price=299.99,
            quantity_available=10
        ),
        InventoryItem(
            product_id="DJ-002", 
            name="DJ Headphones",
            description="Professional headphones",
            price=149.99,
            quantity_available=5
        )
    ]
    test_db.add_all(items)
    test_db.commit()
    for item in items:
        test_db.refresh(item)
    return items

class TestIntegrationAPIEndpoints:
    """Integration tests for the complete API with race condition fixes"""
    
    def test_get_inventory_items(self, client, sample_inventory):
        """Test getting inventory items via API"""
        response = client.get("/api/v1/inventory/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["product_id"] == "DJ-001"
        assert data[1]["product_id"] == "DJ-002"
    
    def test_create_single_order_success(self, client, sample_inventory):
        """Test creating a single order successfully"""
        order_data = {
            "customer_email": "customer@example.com",
            "items": [
                {
                    "inventory_item_id": sample_inventory[0].id,
                    "quantity": 2
                }
            ]
        }
        
        response = client.post("/api/v1/orders/", json=order_data)
        assert response.status_code == 200
        
        order = response.json()
        assert order["customer_email"] == "customer@example.com"
        assert order["status"] == "confirmed"
        assert order["total_amount"] == 599.98  # 2 * 299.99
        
        # Check inventory was updated
        inventory_response = client.get("/api/v1/inventory/")
        inventory = inventory_response.json()
        mixer = next(item for item in inventory if item["product_id"] == "DJ-001")
        assert mixer["quantity_available"] == 8  # 10 - 2
    
    def test_create_order_insufficient_stock(self, client, sample_inventory):
        """Test order fails with insufficient stock"""
        order_data = {
            "customer_email": "customer@example.com",
            "items": [
                {
                    "inventory_item_id": sample_inventory[1].id,
                    "quantity": 10  # More than available (5)
                }
            ]
        }
        
        response = client.post("/api/v1/orders/", json=order_data)
        assert response.status_code == 400
        assert "Insufficient stock" in response.json()["detail"]
    
    def test_inventory_debug_endpoint(self, client, sample_inventory):
        """Test the inventory debug endpoint"""
        response = client.get("/api/v1/inventory/status/debug")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert "version" in data[0]  # Should include version for optimistic locking
    
    def test_get_orders(self, client, sample_inventory):
        """Test getting all orders"""
        # Create an order first
        order_data = {
            "customer_email": "test@example.com",
            "items": [
                {
                    "inventory_item_id": sample_inventory[0].id,
                    "quantity": 1
                }
            ]
        }
        client.post("/api/v1/orders/", json=order_data)
        
        # Get all orders
        response = client.get("/api/v1/orders/")
        assert response.status_code == 200
        orders = response.json()
        assert len(orders) >= 1
        assert orders[0]["customer_email"] == "test@example.com"
    
    def test_get_single_order(self, client, sample_inventory):
        """Test getting a specific order"""
        # Create an order first
        order_data = {
            "customer_email": "specific@example.com",
            "items": [
                {
                    "inventory_item_id": sample_inventory[0].id,
                    "quantity": 1
                }
            ]
        }
        create_response = client.post("/api/v1/orders/", json=order_data)
        order_id = create_response.json()["id"]
        
        # Get the specific order
        response = client.get(f"/api/v1/orders/{order_id}")
        assert response.status_code == 200
        order = response.json()
        assert order["customer_email"] == "specific@example.com"
        assert order["id"] == order_id
    
    def test_get_nonexistent_order(self, client):
        """Test getting a non-existent order returns 404"""
        response = client.get("/api/v1/orders/99999")
        assert response.status_code == 404
        assert "Order not found" in response.json()["detail"]
    
    def test_health_check(self, client):
        """Test basic health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        assert "DJ Agent Backend API" in response.json()["message"]


class TestConcurrencyIntegration:
    """Test concurrent API requests to verify race condition fixes"""
    
    @pytest.mark.asyncio
    async def test_concurrent_orders_via_api(self, client, sample_inventory):
        """
        Test concurrent orders via API endpoints to ensure no race conditions.
        This simulates real-world concurrent API requests.
        """
        import concurrent.futures
        import threading
        
        # Both orders request 3 items from inventory of 5
        # Only one should succeed
        order_data1 = {
            "customer_email": "concurrent1@example.com",
            "items": [
                {
                    "inventory_item_id": sample_inventory[1].id,  # DJ Headphones with 5 stock
                    "quantity": 3
                }
            ]
        }
        
        order_data2 = {
            "customer_email": "concurrent2@example.com", 
            "items": [
                {
                    "inventory_item_id": sample_inventory[1].id,  # Same item
                    "quantity": 3
                }
            ]
        }
        
        # Execute concurrent requests
        def make_order_request(order_data):
            return client.post("/api/v1/orders/", json=order_data)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(make_order_request, order_data1)
            future2 = executor.submit(make_order_request, order_data2)
            
            response1 = future1.result()
            response2 = future2.result()
        
        # Count successful and failed requests
        successful_requests = sum(1 for resp in [response1, response2] if resp.status_code == 200)
        failed_requests = sum(1 for resp in [response1, response2] if resp.status_code == 400)
        
        print(f"Successful API requests: {successful_requests}")
        print(f"Failed API requests: {failed_requests}")
        
        # With race condition fix, only one request should succeed
        assert successful_requests == 1, f"Expected 1 successful request, got {successful_requests}"
        assert failed_requests == 1, f"Expected 1 failed request, got {failed_requests}"
        
        # Check final inventory via API
        inventory_response = client.get("/api/v1/inventory/")
        inventory = inventory_response.json()
        headphones = next(item for item in inventory if item["product_id"] == "DJ-002")
        
        print(f"Final headphones inventory: {headphones['quantity_available']}")
        
        # Should be 2 remaining (5 - 3 = 2), not negative
        assert headphones["quantity_available"] == 2, \
            f"Expected 2 remaining items, got {headphones['quantity_available']}"
        
        print("✓ Concurrent API requests handled correctly - no race condition!")


class TestErrorHandling:
    """Test error handling in various scenarios"""
    
    def test_create_order_invalid_inventory_item(self, client):
        """Test order creation with non-existent inventory item"""
        order_data = {
            "customer_email": "test@example.com",
            "items": [
                {
                    "inventory_item_id": 99999,  # Non-existent
                    "quantity": 1
                }
            ]
        }
        
        response = client.post("/api/v1/orders/", json=order_data)
        assert response.status_code == 400
        assert "not found" in response.json()["detail"]
    
    def test_create_order_invalid_data(self, client):
        """Test order creation with invalid data"""
        order_data = {
            "customer_email": "invalid-email",  # Invalid email format
            "items": []  # Empty items
        }
        
        response = client.post("/api/v1/orders/", json=order_data)
        assert response.status_code == 422  # Validation error