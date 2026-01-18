"""FastAPI application entrypoint for task management API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes
from app.db.engine import create_tables

# Create FastAPI app
app = FastAPI(
    title="Task Management API",
    description="API for managing Instagram post pipeline tasks",
    version="1.0.0",
)

# Enable CORS for local development (will be used with Vue later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(routes.router)


@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup."""
    create_tables()


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Task Management API",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
