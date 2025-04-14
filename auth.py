from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyHeader
import os
import logging

logger = logging.getLogger("audio_service")

X_API_GATEWAY = APIKeyHeader(name="X-From-Gateway", auto_error=False)
GATEWAY_SECRET = os.getenv("GATEWAY_SECRET", "your-secret-shared-key")
ALLOWED_PATHS = [
    "/health",  
    "/metrics" 
]

async def verify_gateway_request(
    request: Request,
    x_api_gateway: str = Depends(X_API_GATEWAY)
):
    """
    Middleware to ensure requests only come from the API Gateway
    or are accessing allowed monitoring endpoints
    """
    # Log incoming headers for debugging
    headers = dict(request.headers)
    logger.debug(f"Auth checking headers: {headers}")
    
    # Allow health check and metrics endpoints without authentication
    for path in ALLOWED_PATHS:
        if request.url.path.startswith(path):
            logger.debug(f"Allowing access to {path} without gateway header")
            return True
    
    # For all other paths, verify the gateway header is present and correct
    if not x_api_gateway or x_api_gateway != "true":
        logger.warning(f"Direct access attempt to {request.url.path} - Missing or invalid X-From-Gateway header")
        raise HTTPException(
            status_code=403,
            detail="Direct access to service is forbidden. Please use the API Gateway."
        )
    
    logger.debug(f"Gateway request verified for {request.url.path}")
    return True