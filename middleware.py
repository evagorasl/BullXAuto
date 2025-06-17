from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from chrome_driver import chrome_driver_manager
import logging

logger = logging.getLogger(__name__)

class CloseDriverMiddleware(BaseHTTPMiddleware):
    """
    Middleware to close Chrome drivers after each API request.
    
    This middleware ensures that Chrome drivers are not kept open unnecessarily.
    The login function in BullXAutomator will be used internally by other functions
    to ensure we're logged in before performing operations.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Process the request
        response = await call_next(request)
        
        # Get the profile name from the request state if available
        profile_name = getattr(request.state, "profile_name", None)
        
        if profile_name:
            path = request.url.path
            logger.info(f"Closing Chrome driver for profile {profile_name} after request to {path}")
            try:
                chrome_driver_manager.close_driver(profile_name)
            except Exception as e:
                logger.error(f"Error closing Chrome driver: {e}")
        
        return response
