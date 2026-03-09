from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
import os
from datetime import datetime

# Create logs directory if it doesn't exist
logs_dir = 'logs'
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# Generate log filename based on current date (format: YYYY-MM-DD.log)
log_filename = os.path.join(logs_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")

# Configure logging with timestamp and file output BEFORE importing any modules
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%d/%m/%Y-%H:%M:%S',
    handlers=[
        logging.FileHandler(log_filename, mode='a', encoding='utf-8'),
        logging.StreamHandler()  # Keep console output as well
    ]
)
logger = logging.getLogger(__name__)

# Suppress noisy APScheduler "Running job / executed successfully" logs
logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)

# Import our modules AFTER logging configuration
from database import create_tables, init_profiles, db_manager
from chrome_driver import chrome_driver_manager
from background_task_monitor import enhanced_order_monitor, queue_processor
from config import config
from routers import secure_router, public_router
from middleware import CloseDriverMiddleware
from auto_monitoring_middleware import AutoMonitoringMiddleware

async def validate_database_consistency():
    """
    Validate database consistency at startup.
    Detects and fixes:
    - Duplicate ACTIVE orders with same bracket_id
    - Stale ACTIVE orders (older than 72 hours)

    This prevents issues from power outages or crashes.
    """
    logger.info("=" * 60)
    logger.info("🔍 STARTUP: Validating database consistency...")
    logger.info("=" * 60)

    # Check for duplicates
    logger.info("Checking for duplicate ACTIVE orders...")
    duplicates = db_manager.detect_duplicate_active_orders()

    if duplicates:
        logger.warning(f"⚠️  Found {len(duplicates)} duplicate order groups")
        logger.info("🔧 Running automatic fix...")

        fixed_count = db_manager.fix_duplicate_active_orders(dry_run=False)
        logger.info(f"✅ Fixed {fixed_count} duplicate orders")
    else:
        logger.info("✅ No duplicate orders found")

    # Check for stale orders
    logger.info("Checking for stale ACTIVE orders (>72 hours)...")
    stale_orders = db_manager.detect_stale_active_orders(max_age_hours=72)

    if stale_orders:
        logger.warning(f"⚠️  Found {len(stale_orders)} stale orders - manual review recommended")
        logger.warning("   These orders may need to be manually marked as COMPLETED or STOPPED")
    else:
        logger.info("✅ No stale orders found")

    logger.info("=" * 60)
    logger.info("✅ Database consistency check complete")
    logger.info("=" * 60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting BullX Automation API...")
    config.APP_START_TIME = datetime.now()

    # Initialize database
    create_tables()
    init_profiles()

    # CRITICAL: Validate database consistency before starting monitoring
    await validate_database_consistency()

    # Start background monitoring for active profiles
    await start_monitoring_for_active_profiles()

    # Start queue processor
    await queue_processor.start()

    logger.info("BullX Automation API started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down BullX Automation API...")
    
    # Stop all background tasks
    await enhanced_order_monitor.stop_monitoring()

    # Stop queue processor
    await queue_processor.stop()

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
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(public_router)
app.include_router(secure_router)

# Mount the frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/dashboard", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.API_RELOAD,  # Default False: auto-reload causes issues with log/db file changes
        log_level=config.LOG_LEVEL.lower()
    )
