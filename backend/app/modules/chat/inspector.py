"""Admin inspector: what the search finds, and what the chat would search for a question, without generating an answer.
/retrieval/research goes through the chat's own steps (validate_question, load_history, RAGWorkflowOrchestrator.inspect_question),
so it cannot show something the chat would not do."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient

from app.modules.auth.user import UserRecord
from app.shared.deps import require_admin, require_notebook
from app.infrastructure.database.mongodb import get_database
from app.infrastructure.database.qdrant import get_qdrant_client
from app.modules.chat.chat import ensure_documents_ready, load_history, validate_question
from app.modules.chat.orchestrator import RAGWorkflowOrchestrator, SourceSelectionError
from app.modules.retrieval.hybrid_search import HybridSearchService

router = APIRouter(prefix="/retrieval", tags=["Retrieval & Search Inspector"])


class SearchRequest(BaseModel):
    notebook_id: str
    query: str
    document_id: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=50)


@router.post("/search")
async def inspect_hybrid_search(
    req: SearchRequest,
    admin: UserRecord = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
):
    await require_notebook(db, req.notebook_id, admin.user_id)
    service = HybridSearchService(db, qdrant)
    results = await service.retrieve_hydrated_chunks(
        query=req.query,
        notebook_id=req.notebook_id,
        document_id=req.document_id,
        top_k=req.top_k,
    )
    return {"query": req.query, "total_retrieved": len(results), "chunks": results}


class ResearchSearchRequest(BaseModel):
    notebook_id: str
    query: str
    document_ids: Optional[List[str]] = None  # the sources selected, as the chat sends them
    mentions: Optional[List[str]] = None  # the @-tagged sources, as the chat sends them


@router.post("/research")
async def inspect_research_retrieval(
    req: ResearchSearchRequest,
    admin: UserRecord = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
):
    """What the chat would do with this question in this notebook (its conversation and topic included): the decision, the rewrite
    of a follow-up, the forced filings, the plan and the excerpts that would be sent to the model. No answer is generated; the paid
    calls the chat makes before answering do happen, and are counted under "llm"."""
    nb = await require_notebook(db, req.notebook_id, admin.user_id)
    chosen, mentions = validate_question(req.document_ids, None, req.mentions, req.query, signed_in=True)
    await ensure_documents_ready(db, req.notebook_id, chosen)
    orchestrator = RAGWorkflowOrchestrator(db, qdrant)
    try:
        return await orchestrator.inspect_question(req.query, req.notebook_id, document_ids=chosen, history=await load_history(db, req.notebook_id),
                                                   mentions=mentions, focus_state=nb.focus_state)
    except SourceSelectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
