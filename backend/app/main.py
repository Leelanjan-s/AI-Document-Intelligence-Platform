import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import redis

from app.core.config import settings
from app.db.database import init_db
from app.utils.s3 import storage
from app.api import auth, documents, metrics

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown lifecycles."""
    logger.info("Initializing system services on startup...")
    
    # 1. Initialize Postgres Database tables
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}")
        
    # 2. Initialize MinIO S3 bucket
    try:
        storage.ensure_bucket_exists()
        logger.info("MinIO bucket check completed.")
    except Exception as e:
        logger.critical(f"Failed to check/create MinIO bucket: {e}")
        
    yield
    logger.info("Shutting down system services...")

app = FastAPI(
    title=settings.APP_NAME,
    description="Production-Grade Applied AI Document Extraction Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom request body size limit checker middleware (15MB limit)
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    max_size = 15 * 1024 * 1024  # 15MB
    content_length = request.headers.get("content-length")
    
    if content_length and int(content_length) > max_size:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"detail": "Request body size exceeds the 15MB ceiling."}
        )
    return await call_next(request)

# Execution latency logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(f"API {request.method} {request.url.path} - {response.status_code} (Duration: {duration:.4f}s)")
    return response

# Register API Routers
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(metrics.router)

@app.get("/health", tags=["Health Check"])
async def health_check():
    """Verify connectivity of PostgreSQL database, Redis queue, and MinIO storage."""
    db_healthy = True
    minio_healthy = True
    redis_healthy = True
    
    # 1. Check MinIO
    if storage.use_local:
        minio_healthy = True
    else:
        try:
            storage.s3_client.list_buckets()
        except Exception as e:
            logger.error(f"Health check failed for MinIO: {e}")
            minio_healthy = False

    # 2. Check Redis
    try:
        r_client = redis.from_url(settings.REDIS_URL, socket_timeout=0.2)
        r_client.ping()
    except Exception as e:
        logger.error(f"Health check failed for Redis: {e}")
        redis_healthy = False
        
    # Note: DB async execution check can be omitted for simple routing or checked if needed
    
    overall_status = "healthy" if db_healthy and minio_healthy and redis_healthy else "degraded"
    # Return 200 OK if both Postgres and MinIO (or its local storage fallback) are healthy
    status_code = status.HTTP_200_OK if db_healthy and minio_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall_status,
            "components": {
                "postgres": "healthy" if db_healthy else "unhealthy",
                "redis": "healthy" if redis_healthy else "unhealthy",
                "minio": "healthy" if minio_healthy else "unhealthy"
            }
        }
    )
