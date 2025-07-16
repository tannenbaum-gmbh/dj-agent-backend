from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class InventoryItemBase(BaseModel):
    product_id: str
    name: str
    description: Optional[str] = None
    price: float
    quantity_available: int

class InventoryItemCreate(InventoryItemBase):
    pass

class InventoryItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    quantity_available: Optional[int] = None

class InventoryItem(InventoryItemBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class OrderItemCreate(BaseModel):
    inventory_item_id: int
    quantity: int

class OrderItem(BaseModel):
    id: int
    inventory_item_id: int
    quantity: int
    unit_price: float
    total_price: float
    inventory_item: Optional[InventoryItem] = None
    
    class Config:
        from_attributes = True

class OrderCreate(BaseModel):
    customer_email: str
    items: List[OrderItemCreate]

class Order(BaseModel):
    id: int
    order_number: str
    customer_email: str
    status: str
    total_amount: float
    created_at: datetime
    updated_at: datetime
    order_items: List[OrderItem] = []
    
    class Config:
        from_attributes = True