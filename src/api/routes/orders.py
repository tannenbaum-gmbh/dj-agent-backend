from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from src.core.database import get_db
from src.models.database import Order as DBOrder
from src.models.schemas import OrderCreate, Order
from src.services.order_service_fixed import OrderProcessingServiceFixed

router = APIRouter()

@router.post("/", response_model=Order)
async def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    """Create a new order with race condition protection"""
    try:
        service = OrderProcessingServiceFixed(db)
        order = await service.process_order(order_data)
        return order
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/", response_model=List[Order])
async def get_orders(db: Session = Depends(get_db)):
    """Get all orders"""
    orders = db.query(DBOrder).all()
    return orders

@router.get("/{order_id}", response_model=Order)
async def get_order(order_id: int, db: Session = Depends(get_db)):
    """Get a specific order"""
    order = db.query(DBOrder).filter(DBOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order