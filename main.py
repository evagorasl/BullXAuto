from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
import os

# Configure logging with timestamp and file output BEFORE importing any modules
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%d/%m/%Y-%H:%M:%S',
    handlers=[
        logging.FileHandler('console_output.txt', mode='a', encoding='utf-8'),
        logging.StreamHandler()  # Keep console output as well
    ]
)
logger = logging.getLogger(__name__)

# Import our modules AFTER logging configuration
from database import create_tables, init_profiles, db_manager
from chrome_driver import chrome_driver_manager
from background_task_monitor import enhanced_order_monitor
from routers import secure_router, public_router
from middleware import CloseDriverMiddleware
from auto_monitoring_middleware import AutoMonitoringMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting BullX Automation API...")
    
    # Initialize database
    create_tables()
    init_profiles()
    
    # Start background monitoring for active profiles
    await start_monitoring_for_active_profiles()
    
    logger.info("BullX Automation API started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down BullX Automation API...")
    
    # Stop all background tasks
    await enhanced_order_monitor.stop_monitoring()
    
    # Close all Chrome drivers
    chrome_driver_manager.close_all_drivers()
    
    logger.info("BullX Automation API shut down successfully")

async def start_monitoring_for_active_profiles():
    """Start background monitoring only for profiles that have active orders"""
    try:
        # Get profiles by checking for active orders
        active_profiles = set()
        active_orders = db_manager.get_active_orders()
        for order in active_orders:
            active_profiles.add(order.profile_name)
        
        # If no active orders, don't start any monitoring yet
        # Monitoring will be started when users make their first API call
        if not active_profiles:
            logger.info("No active profiles with orders found. Background monitoring will start when users make API calls.")
            return
        
        # Start monitoring for profiles with active orders
        for profile_name in active_profiles:
            await enhanced_order_monitor.start_monitoring_for_profile(profile_name)
            logger.info(f"Started background monitoring for profile: {profile_name}")
        
    except Exception as e:
        logger.error(f"Error starting monitoring for active profiles: {e}")
        # Don't fail startup if background monitoring fails

async def ensure_monitoring_for_profile(profile_name: str):
    """Ensure background monitoring is started for a profile when they make API calls"""
    try:
        if profile_name not in enhanced_order_monitor.monitored_profiles:
            await enhanced_order_monitor.start_monitoring_for_profile(profile_name)
            logger.info(f"Started background monitoring for profile: {profile_name} (triggered by API usage)")
    except Exception as e:
        logger.error(f"Error starting monitoring for profile {profile_name}: {e}")

# Create FastAPI app
app = FastAPI(
    title="BullX Automation API",
    description="API for automating trading processes on neo.bullx.io",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(AutoMonitoringMiddleware)
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
