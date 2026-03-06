from fastapi import APIRouter
from fastapi.responses import RedirectResponse
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Create router for public endpoints
router = APIRouter(
    tags=["public"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", include_in_schema=False)
async def root():
    """Redirect root to dashboard"""
    return RedirectResponse(url="/dashboard")

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "BullX Automation API"}
