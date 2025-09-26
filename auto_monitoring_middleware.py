from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

class AutoMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically start background monitoring when users make API calls"""
    
    async def dispatch(self, request: Request, call_next):
        # Process the request normally first
        response = await call_next(request)
        
        # Check if this was a successful authenticated API call
        if (hasattr(request.state, 'profile_name') and 
            request.state.profile_name and 
            response.status_code < 400):
            
            profile_name = request.state.profile_name
            
            # Import here to avoid circular imports
            from main import ensure_monitoring_for_profile
            
            try:
                # Ensure monitoring is started for this profile
                await ensure_monitoring_for_profile(profile_name)
            except Exception as e:
                # Don't fail the request if monitoring setup fails
                logger.error(f"Failed to ensure monitoring for profile {profile_name}: {e}")
        
        return response
