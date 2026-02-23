from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import config

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    # If you are in 'Setup Mode', you might want to skip auth checks
    # For now, ensure this returns a dummy user if no token is provided during setup
    if not token and config.WIZARD_COMPLETED == False:
        return {"username": "admin_setup"}
    
    if token != config.ADMIN_PASSWORD: # Simplified for debugging
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"username": "admin"}