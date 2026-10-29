import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.exceptions import DomainException
from app.core.logging import logger
from app.db.init_admin import setup_admin_and_clean_mocks
from app.db.mongodb import MongoManager
from app.db.qdrant import QdrantManager
from app.services.ingestion.pipeline import IngestionPipeline
from app.services.retrieval.warmup import warm_models


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown event handling."""
    logger.info("Initializing DATN Finance backend application...")
    # Initialize MongoDB connection & indexes
    await MongoManager.connect_to_database()
    # Initialize Qdrant vector client & collection
    await QdrantManager.connect_to_qdrant()

    # Ingestion jobs run in this process: anything still unfinished was killed by the previous shutdown
    try:
        interrupted = await IngestionPipeline.fail_interrupted(MongoManager.db)
        if interrupted:
            logger.warning(f"Marked {interrupted} interrupted ingestion job(s) as failed.")
    except Exception as e:
        logger.warning(f"Could not check interrupted ingestion jobs: {e}")

    # Tự động dọn dẹp tài khoản mock và khởi tạo tài khoản Admin Full Quyền (mật khẩu từ ADMIN_PASSWORD)
    try:
        if (await setup_admin_and_clean_mocks()).get("success"):
            logger.info("Admin user 'admin' ready with full permissions.")
    except Exception as e:
        logger.warning(f"Could not initialize admin user on startup: {e}")

    warmup = asyncio.create_task(warm_models())  # the first question should not pay the model load
    yield
    warmup.cancel()

    logger.info("Shutting down DATN Finance backend application...")
    await MongoManager.close_database_connection()
    await QdrantManager.close_qdrant_connection()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Financial RAG Backend: FastAPI + MongoDB + Qdrant",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Domain Exception Handler
@app.exception_handler(DomainException)
async def domain_exception_handler(request: Request, exc: DomainException):
    logger.warning(f"Domain exception occurred: {exc.message}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": exc.message},
    )


# Include API v1
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"])
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": "mongodb_connected" if MongoManager.db is not None else "disconnected",
        "vector_search": "qdrant_connected" if QdrantManager.client is not None else "disconnected",
    }
