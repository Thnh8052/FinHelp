from fastapi import APIRouter
from app.modules.auth.auth import router as auth_router
from app.modules.admin.admin import router as admin_router
from app.modules.notebooks.notebooks import router as notebooks_router
from app.modules.documents.documents import router as documents_router
from app.modules.chat.chat import router as chat_router
from app.modules.retrieval.retrieval import router as retrieval_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(notebooks_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(retrieval_router)
