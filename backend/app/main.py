import os
# PyTorch CUDA Allocator: chong phan manh VRAM va tu dong nha cache tren Windows
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "max_split_size_mb:128,garbage_collection_threshold:0.8")
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api_router import api_v1_router
from app.core.config import settings
from app.core.error_codes import FIELD_CODES, Code
from app.core.exceptions import DomainException
from app.core.logging import logger
from app.modules.admin.init_admin import ensure_admin
from app.infrastructure.database.mongodb import MongoManager
from app.infrastructure.database.qdrant import QdrantManager
from app.modules.ingestion.pipeline import IngestionPipeline
from app.modules.notebooks.purge import purge_expired_guests
from app.modules.retrieval.warmup import warm_chunk_tokenizer, warm_models
from app.shared.health import check_services
from app.shared.security_headers import SecurityHeaders
from app.shared.unexpected_errors import UnexpectedErrors
from app.shared.upload_limit import UploadSizeLimit


HOUSEKEEPING_SECONDS = 300


async def _housekeeping() -> None:
    """Fail ingestion jobs that stopped moving and remove guest notebooks unused for 24 hours."""
    while True:
        await asyncio.sleep(HOUSEKEEPING_SECONDS)
        try:
            stalled = await IngestionPipeline.fail_stalled(MongoManager.db)
            expired = await purge_expired_guests(MongoManager.db, QdrantManager.client)
            if stalled or expired:
                logger.info(f"Housekeeping: {stalled} stalled job(s) failed, {expired} expired guest notebook(s) removed.")
        except Exception as e:
            logger.warning(f"Housekeeping round failed: {type(e).__name__}: {e}")


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

    # Khởi tạo hoặc cập nhật tài khoản Admin Full Quyền (mật khẩu từ ADMIN_PASSWORD)
    try:
        if (await ensure_admin()).get("success"):
            logger.info("Admin user 'admin' ready with full permissions.")
    except Exception as e:
        logger.warning(f"Could not initialize admin user on startup: {e}")

    await warm_chunk_tokenizer()
    warmup = asyncio.create_task(warm_models())  # the first question should not pay the model load
    housekeeping = asyncio.create_task(_housekeeping())
    yield
    warmup.cancel()
    housekeeping.cancel()

    logger.info("Shutting down DATN Finance backend application...")
    await MongoManager.close_database_connection()
    await QdrantManager.close_qdrant_connection()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Financial RAG Backend: FastAPI + MongoDB + Qdrant",
    lifespan=lifespan,
)

# Added before CORS so that CORS stays the outermost layer: a refused upload and an unforeseen error still carry its headers
app.add_middleware(UploadSizeLimit)
app.add_middleware(UnexpectedErrors)
app.add_middleware(SecurityHeaders)

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
    logger.warning(f"Domain exception occurred: {exc.code} {exc.params}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": exc.code, "params": exc.params}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """A refused body or form. The field validators of the catalog form name their own code and params; any other field gets
    'invalid_field' (no pydantic English reaches the interface)."""
    fields = []
    for err in exc.errors():
        known = err["type"] in FIELD_CODES
        params = {k: v for k, v in (err.get("ctx") or {}).items() if isinstance(v, (int, float, str))} if known else {}
        fields.append({"field": str(err["loc"][-1]) if err.get("loc") else "", "code": err["type"] if known else Code.INVALID_FIELD, "params": params})
    return JSONResponse(status_code=422, content={"detail": {"code": Code.VALIDATION_FAILED, "fields": fields}})


# Include API v1
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"])
async def health_check():
    """The real state of the services: 503 when one of them does not answer."""
    services = await check_services()
    healthy = all(latency is not None for latency in services.values())
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "project": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "database": "mongodb_connected" if services["mongodb"] is not None else "disconnected",
            "vector_search": "qdrant_connected" if services["qdrant"] is not None else "disconnected",
        },
    )
