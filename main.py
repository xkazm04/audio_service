from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import database
import os
import uvicorn
from service_registry import ServiceRegistry
import logging
from prometheus_fastapi_instrumentator import Instrumentator
from contextlib import asynccontextmanager
import time
import json
from routes import api_router  
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("audio_service")

service_registry = ServiceRegistry()

@asynccontextmanager
async def lifespan(app: FastAPI):
    service_registry.register_service()
    service_registry.start_heartbeat()
    yield
    service_registry.deregister_service()
    
app = FastAPI(
    title="Audio service",
    description="Audio and voice processing service",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(api_router, prefix="", tags=["Audio"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


Instrumentator().instrument(app).expose(app)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    headers = dict(request.headers)
    logger.info(f"Incoming request headers: {json.dumps(headers, default=str)}")
    
    allowed_paths = ["/health", "/metrics"]
    is_allowed_path = any(request.url.path.startswith(path) for path in allowed_paths)
    from_gateway = request.headers.get("X-From-Gateway") == "true"
    
    if not (from_gateway or is_allowed_path):
        logger.warning(f"Direct access attempt to {request.url.path} - Forbidden")
        return JSONResponse(status_code=403, content={"detail": "Direct access forbidden"})
    
    start_time = time.time()
    path = request.url.path
    method = request.method
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        log_data = {
            "method": method,
            "path": path,
            "status_code": response.status_code,
            "processing_time_ms": round(process_time * 1000, 2)
        }
        logger.info(f"Request processed: {json.dumps(log_data)}")
        
        return response
    except Exception as e:
        process_time = time.time() - start_time
        log_data = {
            "method": method,
            "path": path,
            "error": str(e),
            "processing_time_ms": round(process_time * 1000, 2)
        }
        logger.error(f"Request error: {json.dumps(log_data)}")
        raise

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()
        

@app.get("/health")
def health_check():
    """Health check endpoint for service discovery"""
    try:
        db = database.SessionLocal()
        db.close()
        return {"status": "healthy"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unhealthy")
    
@app.on_event("startup")
def startup_db_client():
    database.Base.metadata.create_all(bind=database.engine)
    logger.info("Database tables created")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8004))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)