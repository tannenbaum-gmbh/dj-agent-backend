import os
from fastapi import FastAPI
from src.api.routes import orders, inventory

app = FastAPI(
    title="DJ Agent Backend",
    description="AI-powered backend for DJ tools e-commerce",
    version="1.0.0"
)

# Include routers
app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["inventory"])

@app.get("/")
async def root():
    return {"message": "DJ Agent Backend API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)