from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
import os

# Import our modules
from database import create_tables, init_profiles
from chrome_driver import chrome_driver_manager
from background_tasks import start_background_tasks, stop_background_tasks
from routers import secure_router, public_router
from middleware import CloseDriverMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting BullX Automation API...")
    
    # Initialize database
    create_tables()
    init_profiles()
    
    # Start background tasks
    await start_background_tasks()
    
    logger.info("BullX Automation API started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down BullX Automation API...")
    
    # Stop background tasks
    await stop_background_tasks()
    
    # Close all Chrome drivers
    chrome_driver_manager.close_all_drivers()
    
    logger.info("BullX Automation API shut down successfully")

# Create FastAPI app
app = FastAPI(
    title="BullX Automation API",
    description="API for automating trading processes on neo.bullx.io",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(CloseDriverMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Include routers
app.include_router(public_router)
app.include_router(secure_router)

# Mount the frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/dashboard", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    
    @app.get("/", include_in_schema=False)
    async def redirect_to_dashboard():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/dashboard")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
