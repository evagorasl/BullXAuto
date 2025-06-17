from fastapi import APIRouter
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Create router for public endpoints
router = APIRouter(
    tags=["public"],
    responses={404: {"description": "Not found"}},
)

@router.get("/")
async def root():
    """Root endpoint"""
    return {"message": "BullX Automation API is running"}

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "BullX Automation API"}
