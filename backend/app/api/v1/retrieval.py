from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient

from app.api.v1.deps import get_current_user_id, require_notebook
from app.db.mongodb import get_database
from app.db.qdrant import get_qdrant_client
from app.api.v1.chat import ensure_documents_ready, selected_ids
from app.services.query_router.input_policy import decide
from app.services.rag_workflow.orchestrator import RAGWorkflowOrchestrator, SourceSelectionError
from app.services.rag_workflow.replies import sources_message, unlisted_message
from app.services.rag_workflow.scope import document_label, source_info
from app.services.retrieval.hybrid_search import HybridSearchService

router = APIRouter(prefix="/retrieval", tags=["Retrieval & Search Inspector"])


class SearchRequest(BaseModel):
    notebook_id: str
    query: str
    document_id: Optional[str] = None
    top_k: int = 5


@router.post("/search")
async def inspect_hybrid_search(
    req: SearchRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
):
    await require_notebook(db, req.notebook_id, user_id)
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
    document_ids: Optional[List[str]] = None  # the sources selected by the user (required when the notebook has several documents)


@router.post("/research")
async def inspect_research_retrieval(
    req: ResearchSearchRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
):
    """Retrieval only (no answer is generated): the selected sources, the sub-queries / plan, and the chunks that would be sent to the LLM."""
    await require_notebook(db, req.notebook_id, user_id)
    chosen = selected_ids(req.document_ids, None)
    await ensure_documents_ready(db, req.notebook_id, chosen)
    orchestrator = RAGWorkflowOrchestrator(db, qdrant)
    try:
        scope = await orchestrator.resolve_scope(req.notebook_id, chosen)
    except SourceSelectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    ready = await orchestrator._ready_documents(req.notebook_id)
    decision = decide(req.query, [source_info(d) for d in scope], len(ready), [])
    if decision.action not in ("proceed", "answer_per_source_and_ask"):  # the chat endpoint would not search for this question
        return {
            "query": req.query,
            "scope": [{"document_id": d.document_id, "label": document_label(d), "file_name": d.file_name} for d in scope],
            "decision": decision.action,
            "message": sources_message(scope, decision.lang) if decision.action == "list_sources" else decision.message,
            "sub_questions": decision.sub_questions,
            "multi_document": False,
            "plan": [],
            "sub_queries": [],
            "chunks": [],
        }
    unlisted = await orchestrator.find_unlisted(req.query, scope)
    if unlisted:  # same refusal as the chat endpoint: nothing is retrieved for a company outside the selected sources
        return {
            "query": req.query,
            "scope": [{"document_id": d.document_id, "label": document_label(d), "file_name": d.file_name} for d in scope],
            "unlisted_companies": unlisted,
            "message": unlisted_message(unlisted, scope),
            "multi_document": False,
            "plan": [],
            "sub_queries": [],
            "chunks": [],
        }
    found = await orchestrator.retrieve(req.query, req.notebook_id, scope)
    return {
        "query": req.query,
        "scope": [{"document_id": d.document_id, "label": found.labels[d.document_id], "file_name": d.file_name} for d in found.scope],
        "multi_document": bool(found.plan),
        "plan": [{"query": p.query, "documents": [found.labels.get(i, i) for i in p.document_ids] or "all selected"} for p in found.plan],
        "sub_queries": found.sub_queries,
        "chunks": [
            {"rank": n, "document": c.get("document_label") or c["document_id"], "document_id": c["document_id"], "page": c["page"],
             "chunk_type": c["chunk_type"], "score": c["score"], "preview": c["content"][:300]}
            for n, c in enumerate(found.retrieved, 1)
        ],
    }
