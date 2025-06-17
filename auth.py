from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import db_manager
from models import Profile
from typing import Optional

# Security scheme for API key authentication
security = HTTPBearer()

class APIKeyAuth:
    def __init__(self):
        self.db_manager = db_manager
    
    async def get_current_profile(self, credentials: HTTPAuthorizationCredentials = Security(security)) -> Profile:
        """
        Validate API key and return the associated profile
        """
        api_key = credentials.credentials
        
        # Validate API key format
        if not api_key.startswith("bullx_"):
            raise HTTPException(
                status_code=401,
                detail="Invalid API key format",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get profile by API key
        profile = self.db_manager.get_profile_by_api_key(api_key)
        
        if not profile:
            raise HTTPException(
                status_code=401,
                detail="Invalid or inactive API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return profile
    
    async def get_current_profile_optional(self, credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> Optional[Profile]:
        """
        Optional authentication - returns None if no valid API key provided
        """
        if not credentials:
            return None
        
        try:
            return await self.get_current_profile(credentials)
        except HTTPException:
            return None

# Global auth instance
api_key_auth = APIKeyAuth()

# Dependency functions for FastAPI
async def get_current_profile(request: Request, profile: Profile = Depends(api_key_auth.get_current_profile)) -> Profile:
    """Dependency to get current authenticated profile"""
    # Store profile name in request state for middleware
    request.state.profile_name = profile.name
    return profile

async def get_current_profile_optional(profile: Optional[Profile] = Depends(api_key_auth.get_current_profile_optional)) -> Optional[Profile]:
    """Dependency to get current profile (optional)"""
    return profile

def verify_profile_access(requested_profile_name: str, current_profile: Profile) -> bool:
    """
    Verify that the current profile has access to the requested profile operations
    Users can only access their own profile
    """
    return current_profile.name == requested_profile_name

def require_profile_access(requested_profile_name: str, current_profile: Profile = Depends(get_current_profile)):
    """
    Dependency that ensures the current user can only access their own profile
    """
    if not verify_profile_access(requested_profile_name, current_profile):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. You can only access your own profile ({current_profile.name})"
        )
    return current_profile
