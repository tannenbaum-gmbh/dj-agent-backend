"""
FastAPI main application module for DJ Agent Backend
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(
    title="DJ Agent Backend",
    description="AI-powered recommendation engine for DJ tools e-commerce platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "DJ Agent Backend - AI Recommendation Engine"}

@app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes probes"""
    return {"status": "healthy", "service": "dj-agent-backend"}

@app.get("/readiness")
async def readiness_check():
    """Readiness check endpoint for Kubernetes probes"""
    # Add actual readiness checks here (database connectivity, etc.)
    return {"status": "ready", "service": "dj-agent-backend"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)