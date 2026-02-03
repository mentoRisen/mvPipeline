"""FastAPI application entrypoint for task management API."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import routes, auth_routes
from app.db.engine import create_tables
from app.config import OUTPUT_DIR, LOGS_DIR
from app.utils.logging_config import setup_logging

# Setup logging before creating the app
setup_logging()

# Also configure uvicorn access logs
uvicorn_access_log = LOGS_DIR / "uvicorn_access.log"
uvicorn_access_handler = logging.FileHandler(uvicorn_access_log)
uvicorn_access_handler.setLevel(logging.INFO)
uvicorn_access_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))

# Configure uvicorn logger
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addHandler(uvicorn_access_handler)

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


@app.middleware("http")
async def disable_output_cache(request, call_next):
  """Disable browser/proxy caching for files under /output.
  
  This ensures image previews always show the latest version.
  """
  response = await call_next(request)
  if request.url.path.startswith("/output/"):
      response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
      response.headers["Pragma"] = "no-cache"
      response.headers["Expires"] = "0"
  return response


# Include API routes
app.include_router(auth_routes.router)
app.include_router(routes.router)

# Serve generated output files (images) under /output
app.mount(
    "/output",
    StaticFiles(directory=str(OUTPUT_DIR)),
    name="output",
)


@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup."""
    logger = logging.getLogger(__name__)
    logger.info("Initializing database tables...")
    create_tables()
    logger.info("Database tables initialized successfully")


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
    
    # Get logger for this module
    logger = logging.getLogger(__name__)
    logger.info("Starting FastAPI application...")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=None,  # Use our custom logging configuration
    )
