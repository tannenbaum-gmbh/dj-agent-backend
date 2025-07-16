from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from src.core.database import get_db
from src.models.database import InventoryItem as DBInventoryItem
from src.models.schemas import InventoryItem, InventoryItemCreate, InventoryItemUpdate
from src.services.order_service import OrderProcessingService

router = APIRouter()

@router.post("/", response_model=InventoryItem)
async def create_inventory_item(item_data: InventoryItemCreate, db: Session = Depends(get_db)):
    """Create a new inventory item"""
    # Check if product_id already exists
    existing = db.query(DBInventoryItem).filter(
        DBInventoryItem.product_id == item_data.product_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Product ID already exists")
    
    item = DBInventoryItem(**item_data.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.get("/", response_model=List[InventoryItem])
async def get_inventory_items(db: Session = Depends(get_db)):
    """Get all inventory items"""
    items = db.query(DBInventoryItem).all()
    return items

@router.get("/{item_id}", response_model=InventoryItem)
async def get_inventory_item(item_id: int, db: Session = Depends(get_db)):
    """Get a specific inventory item"""
    item = db.query(DBInventoryItem).filter(DBInventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return item

@router.put("/{item_id}", response_model=InventoryItem)
async def update_inventory_item(
    item_id: int, 
    item_data: InventoryItemUpdate, 
    db: Session = Depends(get_db)
):
    """Update an inventory item"""
    item = db.query(DBInventoryItem).filter(DBInventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    for field, value in item_data.dict(exclude_unset=True).items():
        setattr(item, field, value)
    
    db.commit()
    db.refresh(item)
    return item

@router.get("/status/debug")
async def get_inventory_status(db: Session = Depends(get_db)):
    """Get inventory status for debugging race conditions"""
    service = OrderProcessingService(db)
    return service.get_inventory_status()